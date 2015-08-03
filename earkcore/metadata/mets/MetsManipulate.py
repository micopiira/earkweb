from lxml import etree, objectify
import string
import uuid

METS_NS = 'http://www.loc.gov/METS/'
XLINK_NS = 'http://www.w3.org/1999/xlink'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
METS_NSMAP = {'mets': METS_NS, 'xlink': XLINK_NS}
M = objectify.ElementMaker(
    annotate=False,
    namespace=METS_NS,
    nsmap=METS_NSMAP)


def q(ns, v):
    return '{{{}}}{}'.format(ns, v)


def generate_id():
    return 'ID' + str(uuid.uuid4())


def mets_find(root, path, arg, val):
    return root.find('{}[@{}="{}"]'.format(path, arg, val), METS_NSMAP)


def xlink(file_path):
    return {'LOCTYPE': 'URL', q(XLINK_NS, 'href'): file_path, q(XLINK_NS, 'type'): 'simple'}


class Mets:

    def __init__(self, f=None):
        if f is None:
            self.root = M.mets(
                {q(XSI_NS, 'schemaLocation'): METS_NS + ' schemas/IP.xsd'},
                M.metsHdr,
                M.amdSec,
                M.fileSec,
                M.structMap(M.div)
            )
            self.add_agent('ARCHIVIST', 'ORGANIZATION', 'Institution')
        else:
            self.root = objectify.parse(f).getroot()

    def add_agent(self, role, agent_type, name):
        self.root.metsHdr.append(
            M.agent(
                {'ROLE': role, 'TYPE': agent_type},
                M.name(name)
            )
        )

    def add_dmd_sec(self, md_type, file_path):
        gen_id = generate_id()
        self.root.amdSec.addprevious(
            M.dmdSec(
                {'ID': gen_id},
                M.mdRef({'MDTYPE': md_type}, xlink(file_path))
            )
        )
        return gen_id

    def __insert_into_amd_sec(self, md_node, successor_sections, md_type, file_path, adm_id):
        insert_function = self.root.amdSec.append
        for section in successor_sections:
            path = objectify.ObjectPath('amdSec.' + section)
            if path.hasattr(self.root.amdSec):
                insert_function = self.root.amdSec[section].addprevious
                break
        if adm_id == '':
            adm_id = generate_id()
        insert_function(
            md_node(
                {'ID': adm_id},
                M.mdRef({'MDTYPE': md_type}, xlink(file_path))
            )
        )
        return adm_id

    def add_tech_md(self, file_path, adm_id=''):
        return self.__insert_into_amd_sec(M.techMD, ['rightsMD', 'sourceMD', 'digiprovMD'], 'PREMIS:OBJECT', file_path, adm_id)

    def add_rights_md(self, file_path, adm_id=''):
        return self.__insert_into_amd_sec(M.rightsMD, ['sourceMD', 'digiprovMD'], 'PREMIS:RIGHTS', file_path, adm_id)

    def add_digiprov_md(self, file_path, adm_id=''):
        return self.__insert_into_amd_sec(M.digiprovMD, [], 'PREMIS:EVENT', file_path, adm_id)

    def find_amd_md(self, adm_id):
        return mets_find(self.root.amdSec, '*', 'ID', adm_id)

    def find_file_grp(self, grp_use):
        return mets_find(self.root.fileSec, 'mets:fileGrp', 'USE', grp_use)

    def add_file_grp(self, grp_use):
        self.root.fileSec.append(
            M.fileGrp({'USE': grp_use})
        )
        self.root.structMap.div.append(
            M.div({'LABEL': grp_use})
        )

    def add_file(self, grp_use, file_path, adm_ids):
        self.add_file_node(
            grp_use,
            M.file(
                {'ID': generate_id(), 'ADMID': string.join(adm_ids)},
                M.FLocat(xlink(file_path))
            )
        )

    def add_file_node(self, grp_use, file_node):
        if self.find_file_grp(grp_use) is None:
            self.add_file_grp(grp_use)
        file_grp = self.find_file_grp(grp_use)
        file_grp.append(file_node)
        div = mets_find(self.root.structMap.div, 'mets:div', 'LABEL', grp_use)
        div.append(
            M.fptr({'FILEID': file_node.get('ID')})
        )

    def copy_file_info(self, aip_mets, filepath):
        f_locat = mets_find(aip_mets.root.fileSec, './/mets:file/mets:FLocat', 'xlink:href', 'file://.' + filepath)
        file_node = f_locat.getparent()
        self.add_file_node(file_node.getparent().get('USE'), file_node)
        for adm_id in string.split(file_node.get('ADMID')):
            amd_md = aip_mets.find_amd_md(adm_id)
            if self.find_amd_md(adm_id) is None:
                if amd_md.tag == q(METS_NS, 'techMD'):
                    self.add_tech_md(amd_md.mdRef.get(q(XLINK_NS, 'href')), adm_id)
                elif amd_md.tag == q(METS_NS, 'rightsMD'):
                    self.add_rights_md(amd_md.mdRef.get(q(XLINK_NS, 'href')), adm_id)
                elif amd_md.tag == q(METS_NS, 'digiprovMD'):
                    self.add_digiprov_md(amd_md.mdRef.get(q(XLINK_NS, 'href')), adm_id)

    def validate(self):
        with open('../../Downloads/mets.xsd', 'r') as f:
            xmlschema = etree.XMLSchema(file=f)
        return xmlschema.validate(self.root)

    def __str__(self):
        return etree.tostring(self.root, encoding='UTF-8', pretty_print=True, xml_declaration=True)


def main():
    with open('earkresources/AIP-test/AIP-compound/METS.xml', 'r') as mets_file:
        my_mets = Mets()
    my_mets.add_dmd_sec('EAD', 'file://./metadata/EAD.xml')
    admids = []
    admids.append(my_mets.add_tech_md('file://./metadata/PREMIS.xml#Obj'))
    admids.append(my_mets.add_digiprov_md('file://./metadata/PREMIS.xml#Ingest'))
    admids.append(my_mets.add_rights_md('file://./metadata/PREMIS.xml#Right'))
    my_mets.add_file_grp('submission')
    my_mets.add_file('submission', 'file://./content/data.sql', admids)
    my_mets.root.set('TYPE', 'DIP')
    print my_mets
    print my_mets.validate()

if __name__ == "__main__":
    main()
