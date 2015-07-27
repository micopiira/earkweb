import tasks
import inspect
import pydoc
import re
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "earkweb.settings")

import django
django.setup()

from workflow.models import WorkflowModules

class Param(object):
    def __init__(self, type, name, descr):
        self.type = type
        self.name = name
        self.descr = descr

class InputParam(Param):
    pass

class ReturnParam(Param):
    pass

class TaskScanner(object):
    """
    Scan tasks module for Celery tasks. The run method documentation is parsed to provide
    input parameter documentation.
    """

    task_modules = dict()

    def __init__(self, taskmodule):
        """
        Scanning celery tasks and parsing run method documentation is done here in the constructor.
        """
        self.taskmodule = taskmodule
        methodList = [item for item in dir(taskmodule)]
        for item in methodList:
            if inspect.isclass(getattr(tasks, item)) and str(item) != "Task":
                c = getattr(tasks, item)
                runmethod = getattr(c, "run")
                rundoc = runmethod.__doc__
                params = []
                doclist = rundoc.split('\n')
                paramline = ""
                for dlitem in doclist:
                    paramline += dlitem
                    if "@param" in dlitem:
                        match = re.search('@type (?P<tpname>.*): (?P<datatype>.*)@param (?P<ppname>.*): (?P<description>.*)', paramline)
                        type = match.group('datatype').strip()
                        name = match.group('tpname').strip()
                        descr = match.group('description').strip()
                        params.append(InputParam(type, name, descr))
                        paramline = ""
                    elif "@return:" in dlitem:
                        match = re.search('@rtype:\s*(?P<rtype>.*)@return:\s*(?P<descr>.*)', paramline)
                        type = match.group('rtype').strip()
                        descr = match.group('descr').strip()
                        params.append(ReturnParam(type, None, descr))
                        paramline = ""
                self.task_modules[str(item)] = params

class WireItLanguageModules(object):
    """
    Build language modules from task module objects based on JSON template.
    """

    def __init__(self, task_modules):
        self.task_modules = task_modules

    language_module_template = """
    {
        "name": "%(module_name)s",
        "container": {
            "xtype": "WireIt.FormContainer",
            "title": "%(module_name)s",
            "icon": "/static/earkweb/workflow/wireit/res/icons/valid-xml.png",
            "collapsible": true,
            "drawingMethod": "arrows",
            "fields": [
                %(input_params)s
            ],
            "terminals": [
                {"name": "_INPUT", "direction": [0,0], "offsetPosition": {"left": 160, "top": -13 },"ddConfig": {"type": "input","allowedTypes": ["output"]}, "nMaxWires": 1,  "drawingMethod": "arrows" },
                {"name": "_OUTPUT", "direction": [0,0], "offsetPosition": {"left": 160, "bottom": -13 },"ddConfig": {"type": "output","allowedTypes": ["input"]}}
            ],
            "legend": "%(module_name)s",
            "drawingMethod": "arrows"
        }
    },
    """

    language_module_inputs_template = """
        {"type":"%(type)s", "inputParams": {"label": "%(descr)s", "name": "%(name)s"}},
    """

    def register_language_modules(self):
        """
        Register tasks as language modules in the database. All records are deleted first,
        then available celery tasks are stored as language modules.
        """
        WorkflowModules.objects.all().delete()
        for module_name, module_params in self.task_modules.iteritems():
            input_params = ""
            for module_param in module_params:
                if isinstance(module_param, InputParam):
                    input_params += self.language_module_inputs_template % { 'name': module_param.name, 'descr': module_param.descr, 'type': module_param.type}
            model_def = self.language_module_template % { 'module_name': module_name, 'input_params': input_params }
            workflow_module = WorkflowModules(identifier=module_name, model_definition=model_def)
            workflow_module.save()



def main():
    task_modules = TaskScanner(tasks).task_modules
    wirelangmod = WireItLanguageModules(task_modules)
    wirelangmod.register_language_modules()


if __name__ == "__main__":
    main()