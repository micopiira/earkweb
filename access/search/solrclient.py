"""Solr client"""
import logging
import re
from urllib.parse import urlencode
from urllib.request import urlopen, Request

import pytz
from eatb.format.formatidentification import FormatIdentification
from eatb.utils import randomutils
from eatb.utils.datetime import current_date
from datetime import datetime
from access.search.solrdocparams import SolrDocParams
from config.configuration import verify_certificate, representations_directory, metadata_directory

logger = logging.getLogger(__name__)
import os
import json
import shutil
import urllib

import lxml.etree as etree
import unittest

import requests


def default_reporter(percent):
    print("\rProgress: {percent:3.0f}%".format(percent=percent))


class SolrClient(object):

    ffid = None

    def __init__(self, solr_server, collection):
        """
        Constructor to initialise solr client API URL

        @type       solr_server: SolrServer
        @param      solr_server: Solr server

        @type       collection: string
        @param      collection: Collection identifier, e.g. "samplecollection"
        """
        base_url = solr_server.get_base_url()
        if base_url[-1] != '/':
            base_url += '/'
        self.url = base_url + collection
        self.ffid = FormatIdentification()

    def select_params_suffix(self, params_suffix, rows=1000, start=0):
        """
        Search Solr, return URL and JSON response

        @type       params: string
        @param      params: Parameter suffix

        @rtype: string, int
        @return: Return url and return code
        """
        url = self.url + '/select?q=%s&rows=%d&start=%d&wt=json' % (urllib.quote(params_suffix), rows, start)
        conn = urlopen(url)
        return url, json.load(conn)

    def select(self, params):
        """
        Search Solr, return URL and JSON response

        @type       params: string
        @param      params: Query parameters

        @rtype: string, int
        @return: Return url and return code
        """
        params['wt'] = 'json'
        url = self.url + '/select?' + urllib.urlencode(params)
        conn = urlopen(url)
        return url, json.load(conn)

    def delete(self, query):
        """
        Delete query result documents

        @type       query: string
        @param      query: query

        @rtype: string, int
        @return: Return url and return code
        """
        params = {}
        url = self.url + '/update?' + urllib.urlencode(params)
        request = Request(url)
        request.add_header('Content-Type', 'text/xml; charset=utf-8')
        request.add_data('<delete><query>{0}</query></delete>'.format(query))
        response = urlopen(request).read()
        status = etree.XML(response).findtext('lst/int')
        return url, status

    def update(self, docs):
        """
        Post a list of documents

        @type       docs: list
        @param      docs: List of solr documents

        @rtype: string, int
        @return: Return url and return code
        """
        url = self.url + '/update?commit=true'
        add_xml = etree.Element('add')
        for doc in docs:
            xdoc = etree.SubElement(add_xml, 'doc')
            for key, value in doc.items():
                if value:
                    field = etree.Element('field', name=key)
                    field.text = str(value)
                    xdoc.append(field)
        request = Request(url)
        request.add_header('Content-Type', 'text/xml; charset=utf-8')
        request.data =etree.tostring(add_xml, pretty_print=True)
        response = urlopen(request).read()
        status = etree.XML(response).findtext('lst/int')
        return url, status

    def post_file_document(self, file_path, identifier, entry):
        """
        Iterate over tar file and post documents it contains to Solr API (extract)

        @type       file_path: string
        @param      file_path: Absolute path to file

        @type       identifier: string
        @param      identifier: Identifier of the tar package

        @type       entry: string
        @param      entry: entry name
        """
        puid = self.ffid.identify_file(file_path)
        content_type = self.ffid.get_mime_for_puid(puid)
        docs = []
        document = {"package": identifier, "path": entry, "content_type": content_type}
        docs.append(document)
        _, status = self.update(docs)
        return status

    def post_tar_file(self, tar_file_path, identifier, version, progress_reporter=default_reporter):
        """
        Iterate over tar file and post documents it contains to Solr API (extract)

        @type       tar_file_path: string
        @param      tar_file_path: Absolute path to tar file

        @type       identifier: string
        @param      identifier: Identifier of the tar package

        @rtype: list(dict(string, int))
        @return: Return list of urls and return codes
        """
        progress_reporter(0)
        import tarfile
        tfile = tarfile.open(tar_file_path, 'r')
        extract_dir = '/tmp/temp-' + randomutils.randomword(10)
        results = []

        numfiles = sum(1 for tarinfo in tfile if tarinfo.isreg())
        logger.debug("Number of files in tarfile: %s " % numfiles)

        num = 0

        for t in tfile:
            tfile.extract(t, extract_dir)
            afile = os.path.join(extract_dir, t.name)

            if os.path.exists(afile) and os.path.isfile(afile):
                params = SolrDocParams(afile).get_params()
                params['literal.package'] = identifier
                params['literal.path'] = t.name
                params['literal.size'] = t.size
                params['literal.is_metadata'] = bool(re.search("/%s/" % metadata_directory, afile))
                params['literal.is_content_data'] = bool(re.search("/%s/[-0-9a-z]{36,36}/data" % representations_directory, afile))
                params['literal.indexdate'] = current_date(time_zone_id='UTC')
                params['literal.archivedate'] = datetime.fromtimestamp(os.path.getctime(tar_file_path)).astimezone(pytz.UTC)
                params['literal.version'] = int(re.search(r'\d+', version).group(0))
                files = {'file': ('userfile', open(afile, 'rb'))}
                post_url = '%s/update/extract?%s' % (self.url, urlencode(params))
                response = requests.post(post_url, files=files, verify=verify_certificate)
                result = {"url": post_url, "status": response.status_code}
                if response.status_code != 200:
                    status = self.post_file_document(afile, identifier, t.name)
                    if status == 200:
                        logger.info("posting file failed for url '%s' with status code: %d (posted plain document instead)" % (post_url, response.status_code))
                    else:
                        logger.info("Unable to create document for url '%s'" % (post_url))
                results.append(result)
                num += 1
                percent = num * 100 / numfiles
                progress_reporter(percent)
            self.commit()
            logger.debug("Files extracted to %s" % extract_dir)
            shutil.rmtree(extract_dir)
        progress_reporter(100)
        return results

    def commit(self):
        """
        Commit changes to Solr

        @rtype: string, int
        @return: Return url and return code
        """
        url = self.url + '/update?commit=true'
        response = urlopen(url)
        return url, response.code


class TestSolr(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    # def test_solr_post_document(self):
    #     slr = SolrClient("http://localhost:8983/solr/", "samplecollection")
    #     docs = []
    #     document = {"id":"1234abcde",
    #             "cat":"journal",
    #             "name":"Experiments on the go",
    #             "genre_s":"science"}
    #     docs.append(document)
    #     slr.update(docs)
    #     slr.commit()

    # def test_extract(self):
    #     slr = SolrClient("http://localhost:8983/solr/", "samplecollection")
    #     tar_file_path = "/opt/python_wsgi_apps/earkweb/testresources/storage-test/bar.tar"
    #     identifier = "739f9c5f-c402-42af-a18b-3d0bdc4e8751"
    #     results = slr.post_tar_file(tar_file_path, identifier)
    #     print results

if __name__ == '__main__':
    unittest.main()
