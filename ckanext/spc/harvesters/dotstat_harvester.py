# -*- coding: utf-8 -*-
import requests
import traceback
from bs4 import BeautifulSoup

from ckan.lib.helpers import json
from ckan.lib.munge import munge_tag
from ckanext.harvest.model import HarvestObject
from ckanext.harvest.harvesters import HarvesterBase
from ckan.logic import get_action
from pylons import config

import logging
log = logging.getLogger(__name__)


class SpcDotStatHarvester(HarvesterBase):
    '''
    The harvester for DDI data
    '''

    HARVEST_USER = 'harvest'

    ACCESS_TYPES = {
        '': '',
        'direct_access': 1,
        'public_use': 2,
        'licensed': 3,
        'data_enclave': 4,
        'data_external': 5,
        'no_data_available': 6,
        'open_data': 7,
    }

    # CKAN attributes, but we're missing heaps (they'd all just be stored in 'extras')
    #   could be a big problem point
    DEFAULT_ATTRIBUTES = [
        'id',
        'name',
        'publisher_name',
        'url',
        'version',
        'notes',
        'extras',
    ]

    def info(self):
        return {
            'name': 'dotstat',
            'title': '.Stat harvester for SDMX',
            'description': (
                'Harvests SDMX data from a .Stat instance '
            ),
            'form_config_interface': 'Text'
        }

    def _set_config(self, config_str):
        if config_str:
            self.config = json.loads(config_str)
        else:
            self.config = {}

        if 'user' not in self.config:
            self.config['user'] = self.HARVEST_USER

        log.debug('Using config: %r' % self.config)

    def get_endpoints(self, base_url):
        endpoints = []
        resources_url = base_url + 'all'
        resp = requests.get(resources_url)
        #print(resp.text)
        soup = BeautifulSoup(resp.text, 'xml')
        #print(soup)
        for name in soup.findAll('Dataflow'):
            endpoints.append(name['id'])
        return endpoints

    def gather_stage(self, harvest_job):
        log.debug('In NadaHarvester gather_stage')
        api_url = None

        # Go to i.e. https://microdata.pacificdata.org/index.php/api/v2/catalog/search/format/json?page=1
        #   and get the json
        '''
        {"rows":[{"id":"639","idno":"SPC_ASM_2018_BAS_v01_M_DEVELOPMENT","title":"Business Survey 2018",
                  "nation":"American Samoa","authoring_entity":"American Samoa Department of Commerce",
                  "form_model":"data_na","year_start":"2018","year_end":"2018","repositoryid":"ASM",
                  "link_da":null,"repo_title":"American Samoa","created":"1566780425","changed":"1566780813",
                  "total_views":"23","total_downloads":"0"},
                 {"id":"703","idno":"SPC_ASM_2017_ECS_v01_M_DEVELOPMENT",
                  "title":"Economic census 2017","nation":"American Samoa","authoring_entity":"US Census ....}]}
        '''
        # For each row of data, use its ID as the GUID and save a harvest object
        # Return a list of all these new harvest jobs
        #
        try:
            harvest_obj_ids = []
            self._set_config(harvest_job.source.config)
            # base_url = 'https://stats.pacificdata.org/data-nsi/Rest/dataflow/SPC/'
            base_url = harvest_job.source.url

            try:
                # Get list of endpoint ids
                endpoints = self.get_endpoints(base_url)
                '''
                api_url = base_url + self._get_search_api(
                self.config['access_type'],
                page
                )
                '''
            except (AccessTypeNotAvailableError, KeyError):
                log.debug('Endpoint function failed')
                
                '''
                log.debug('Gather datasets from: %s' % base_url)

                headers = {
                    'User-agent': 'Mozilla/5.0'
                }
                r = requests.get(api_url, headers=headers)
                data = r.json()

                log.debug('JSON data from %s: %r' % (api_url, data))
                '''

            # Make a harvest object for each dataset
            # Set the GUID to the dataset's ID (DF_SDG etc.)
            for i, end in enumerate(endpoints):
                harvest_obj = HarvestObject(
                    guid=end,
                    job=harvest_job
                )
                harvest_obj.save()
                harvest_obj_ids.append(harvest_obj.id)

                '''
                for row in data['rows']:
                    harvest_obj = HarvestObject(
                        guid=row['id'],
                        job=harvest_job
                    )
                    harvest_obj.save()
                    harvest_obj_ids.append(harvest_obj.id)
                page += 1
                row_count = int(data['offset']) + int(data['limit'])
                '''
            log.debug('IDs: %r' % harvest_obj_ids)

            return harvest_obj_ids
        except Exception, e:
            self._save_gather_error(
                'Unable to get content for URL: %s: %s / %s'
                % (base_url, str(e), traceback.format_exc()),
                harvest_job
            )

    # Get the DDI formatted resource for the GUID
    #   i.e. https://microdata.pacificdata.org/index.php/catalog/ddi/639
    #   returns a download containing DDI resource
    # Put this in harvest_object's 'content' as text
    def fetch_stage(self, harvest_object):
        log.debug('In DotStatHarvester fetch_stage')
        self._set_config(harvest_object.job.source.config)

        if not harvest_object:
            log.error('No harvest object received')
            self._save_object_error(
                'No harvest object received',
                harvest_object
            )
            return False

        base_url = harvest_object.source.url
        ddi_api_url = None
        meta_suffix = '1.0/?references=all&detail=referencepartial'
        metadata_url = '{}{}/{}'.format(base_url, harvest_object.guid, meta_suffix)

        try:
            #log.debug('Empty object: ' + harvest_object.content)
            endpoints_metadata = list()
            #print(endpoints_metadata)
            #endpoints = get_endpoints(base_url)
            log.debug('Fetching content from %s' % metadata_url)
            meta = requests.get(metadata_url)
            meta.encoding = 'utf-8'
            # Dump page contents into harvest object content
            #soup = BeautifulSoup(meta.text, 'xml')
            harvest_object.content = meta.text
            #log.debug('Filled object: ' + harvest_object.content)
            harvest_object.save()
            log.debug('successfully processed ' + harvest_object.guid)
            return True

            '''
            ddi_api_url = base_url + self._get_ddi_api(harvest_object.guid)
            log.debug('Fetching content from %s' % ddi_api_url)
            headers = {
                'User-agent': 'Mozilla/5.0'
            }
            r = requests.get(ddi_api_url, headers=headers)
            r.encoding = 'utf-8'
            harvest_object.content = r.text
            harvest_object.save()
            log.debug('successfully processed ' + harvest_object.guid)
            return True
            '''
        except Exception, e:
            self._save_object_error(
                (
                    'Unable to get content for package: %s: %r / %s'
                    % (metadata_url, e, traceback.format_exc())
                ),
                harvest_object
            )
            return False

    def import_stage(self, harvest_object):
        log.debug('In DotStatHarvester import_stage')
        self._set_config(harvest_object.job.source.config)

        if not harvest_object:
            log.error('No harvest object received')
            self._save_object_error(
                'No harvest object received',
                harvest_object
            )
            return False

        try:
            base_url = harvest_object.source.url

            # Get a class which maps ckan metadata to the DDI equivalent
            # Extract metadata content from XML DDI
            #   put it in a dictionary
            #pkg_dict = ckan_metadata.load(harvest_object.content)

            # Really not sure if this will work lol
            soup = BeautifulSoup(harvest_object.content, 'xml')

            #print(meta.text)
            pkg_dict = {}
            pkg_dict['id'] = harvest_object.guid
            
            # Get owner_org if there is one
            source_dataset = get_action('package_show')({
                'ignore_auth': True
            }, {
                'id': harvest_object.source.id
            })
            owner_org = source_dataset.get('owner_org')
            pkg_dict['owner_org'] = owner_org

            # Match other fields
            structure = soup.find('Dataflow', attrs= {'id': pkg_dict['id']})
            pkg_dict['title'] = structure.find('Name').text
            pkg_dict['publisher_name'] = structure['agencyID']
            pkg_dict['version'] = structure['version']
            # Need to change url
            pkg_dict['url'] = base_url
            pkg_dict['notes'] = 'Where to get description?'
            
            '''
            This 'extras' code isn't really scalable
            You need to know exactly what you want, what format etc.
            i.e. it's not easy to standardise
            For SDG, get Indicators from Codelist SDG_SERIES
            For POCKET, get Summaries from Codelist CL_POCKET
            For IMTS, get Commodity Code & Mode of Transport
            '''
            if pkg_dict['id'] == 'DF_SDG':
                pkg_dict['alternate_identifier'] = []
                #pkg_dict['extras'][0]['key'] = 'Indicators'
                #pkg_dict['extras'][0]['value'] = []
                codelist = soup.find('Codelist', attrs={'id': 'CL_SDG_SERIES'})
                for indic in codelist.findAll('Name'):
                    if indic.text == 'SDG Indicator or Series':
                        continue
                    pkg_dict['alternate_identifier'].append(indic.text)

            log.debug('package dict: %s' % pkg_dict)
            # Now create the package
            return self._create_or_update_package(pkg_dict, harvest_object,
                package_dict_form='package_show')
        except Exception, e:
            self._save_object_error(
                (
                    'Exception in import stage: %r / %s'
                    % (e, traceback.format_exc())
                ),
                harvest_object
            )
            return False

class AccessTypeNotAvailableError(Exception):
    pass

