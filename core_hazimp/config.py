# -*- coding: utf-8 -*-

# Copyright (C) 2012-2013  Duncan Gray

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Functions concerning the yaml configuration file.
"""

import os
import yaml
import copy

from core_hazimp.calcs.calcs import CALCS, FLOOR_HEIGHT, FLOOR_HEIGHT_CALC
from core_hazimp.jobs.jobs import (JOBS, LOADRASTER, LOADCSVEXPOSURE,
                                   LOADXMLVULNERABILITY, SIMPLELINKER,
                                   SELECTVULNFUNCTION,
                                   LOOKUP, SAVEALL, CONSTANT)
from core_hazimp.calcs.calcs import STRUCT_LOSS, WATER_DEPTH
from core_hazimp import misc
from core_hazimp import spell_check
from core_hazimp import workflow

DEFAULT = 'default'
LOADWINDTCRM = 'load_wind_ascii'
LOADFLOODASCII = 'load_flood_ascii'
TEMPLATE = 'template'
WINDV3 = 'wind_v3'
FLOODFABRICV2 = 'flood_fabric_v2'
SAVE = 'save'


# The complete list of first level key names in the post template config dic
CONFIGKEYS = list(JOBS.keys()) + list(CALCS.keys())
SPELLCHECK = spell_check.SpellCheck(CONFIGKEYS)


def read_file(file_name):
    """
    Read the configuration file and return the info as a dictionary.

    :param file_name: The yaml file.
    :returns: A dictionary of the configuration file
    """
    config_file_handle = open(file_name, 'r')
    config_inf = yaml.load(config_file_handle)
    if isinstance(config_inf, dict):
        config_dic = config_inf
    else:
        # Assume a list of dictionaries
        config_dic = {}
        for form in config_inf:
            config_dic.update(form)
    return config_dic


def read_config_file(file_name):
    """
    Read the configuration file and return the info as a list.

    :param file_name: The yaml file.
    :returns: A list of the configuration file
    """
    config_file_handle = open(file_name, 'r')
    the_conf = yaml.load(config_file_handle)
    # print "the_conf", the_conf
    return the_conf


def instance_builder(config_list):
    """
    From the configuration list build and knowing
    the template, build the the job instances
    and add attributes in the config to the instances.

    :param config_list: A list describing the simulation.
    :returns: A list of job instances to process over.
    """
    # print "config_list", config_list

    # Check that each element in the list is a single key dictionary.
    for jobcalc_dic in config_list:
        if not len(jobcalc_dic) == 1:
            msg = '\nConfig bad format. Forgotten dash? Two key dictionary?\n'
            msg += '%s \n' % jobcalc_dic
            raise RuntimeError(msg)

    try:
        template = config_list[0][TEMPLATE]
        del config_list[0]
    except KeyError:
        template = DEFAULT
    try:
        reader_function = READERS[str(template)]
    except KeyError:
        raise RuntimeError(
            'Invalid template name, %s in config file.' % template)

    jobs = reader_function(config_list)
    return jobs


def template_builder(config_dic):
    """
    From the configuration dictionary build and knowing
    the template, build the the job list
    and add predefined info to the config_dic.

    :param config_dic: A dictionary describing the simulation.
    :returns: A list of jobs to process over.
        ** The config_dic isn't returned, but it is modified.
    """
    try:
        template = config_dic[TEMPLATE]
        del config_dic[TEMPLATE]
    except KeyError:
        template = DEFAULT

    try:
        reader_function = READERS[str(template)]
    except KeyError:
        raise RuntimeError(
            'Invalid template name, %s in config file.' % template)

    jobs = reader_function(config_dic)
    return jobs


def _reader2(config_list):
    """
    From an untemplated configuration list build the job list.

    :param config_list: A list describing the simulation.
    :returns: A list of jobs to process over.
    """
    job_insts = []

    for jobcalc_dic in config_list:
        new_string = jobcalc_dic.keys()[0]
        atts = jobcalc_dic[new_string]
        _add_job(job_insts, new_string, atts=atts)

    # For testing
    if False:
        for job in job_insts:
            print "*******************************************"
            print "job.job_instance", job.job_instance
            print "job.atts_to_add", job.atts_to_add
    return job_insts


def _wind_v3_reader(config_list):
    """
    From a wind configuration list build the job list.

    :param config_list: A list describing the simulation.
    :returns: A list of jobs to process over.
    """
    job_insts = []

    atts = find_atts(config_list, LOADCSVEXPOSURE)
    _add_job(job_insts, LOADCSVEXPOSURE, atts)

    file_list = find_atts(config_list, LOADWINDTCRM)
    atts = {'file_list': file_list,
            'attribute_label': '0.2s gust at 10m height m/s'}
    _add_job(job_insts, LOADRASTER, atts)

    vul_filename = os.path.join(misc.RESOURCE_DIR,
                                'synthetic_domestic_wind_vul_curves.xml')
    _add_job(job_insts, LOADXMLVULNERABILITY, {'file_name': vul_filename})

    # The vulnerabilitySetID from the nrml file = 'domestic_flood_2012'
    # The column title in the exposure file = 'WIND_VULNERABILITY_FUNCTION_ID'
    atts = {'vul_functions_in_exposure': {
            'domestic_wind_2012':
            'WIND_VULNERABILITY_FUNCTION_ID'}}
    _add_job(job_insts, SIMPLELINKER, atts)

    atts = {'variability_method': {
            'domestic_wind_2012': 'mean'}}
    _add_job(job_insts, SELECTVULNFUNCTION, atts)

    _add_job(job_insts, LOOKUP)
    _add_job(job_insts, STRUCT_LOSS)

    file_name = find_atts(config_list, SAVE)
    _add_job(job_insts, SAVEALL, {'file_name': file_name})

    return job_insts


def find_atts(config_list, job):
    """
    Find the attributes on a job in a config_list.

    :param config_list:
    :param job: The job name as a string.
    """
    atts = None
    for ele in config_list:
        if job in ele:
            atts = ele[job]
    if atts is None:
        msg = '\nMandatory key not found in config file; %s\n' % job
        raise RuntimeError(msg)
    return atts


def _flood_fabric_v2_reader(config_list):
    """
    This function does two things;
       * From a flood fabric template v1 configuration dictionary
       build the job list.
       * Set up the attributes of the jobs and calc's specifically
       for a flood study.
    :param config_list: A list describing the simulation.
    :returns: A list of jobs to process over.
    """
    job_insts = []

    atts = find_atts(config_list, LOADCSVEXPOSURE)
    _add_job(job_insts, LOADCSVEXPOSURE, atts)

    file_list = find_atts(config_list, LOADFLOODASCII)
    atts = {'file_list': file_list, 'attribute_label': WATER_DEPTH}
    _add_job(job_insts, LOADRASTER, atts)
    vul_filename = os.path.join(misc.RESOURCE_DIR,
                                'fabric_flood_avg_curve.xml')
    _add_job(job_insts, LOADXMLVULNERABILITY, {'file_name': vul_filename})

    floor_height_value = find_atts(config_list, FLOOR_HEIGHT)
    atts = {'var': FLOOR_HEIGHT, 'value': floor_height_value}
    _add_job(job_insts, CONSTANT, atts)

    _add_job(job_insts, FLOOR_HEIGHT_CALC)

    # The vulnerabilitySetID from the nrml file = 'domestic_flood_2012'
    # The column title in the exposure file = 'WIND_VULNERABILITY_FUNCTION_ID'
    atts = {'vul_functions_in_exposure': {
            'structural_domestic_flood_2012':
            'FABRIC_FLOOD_FUNCTION_ID'}}
    _add_job(job_insts, SIMPLELINKER, atts)

    atts = {'variability_method': {
            'structural_domestic_flood_2012': 'mean'}}
    _add_job(job_insts, SELECTVULNFUNCTION, atts)

    _add_job(job_insts, LOOKUP)
    _add_job(job_insts, STRUCT_LOSS)

    file_name = find_atts(config_list, SAVE)
    _add_job(job_insts, SAVEALL, {'file_name': file_name})

    return job_insts


def _add_job(jobs, new_job, atts=None):
    """
    Given a list of jobs, add a new job and it's att's to the job.

    :param jobs: A list of jobs.
    :param new_job: The new job, as a string.
    :param atts: The attributes of the new job.
    """
    if atts is None:
        atts = {}
    job_inst = _get_job_or_calc(new_job)
    validate_job_instance(job_inst, atts)
    caj = workflow.ConfigAwareJob(job_inst,
                                  atts_to_add=atts)
    jobs.append(caj)


def get_job_or_calcs(job_names):
    """
    Given a list of job or calc names, return a list of job or calc
    instances.

    :param job_names: a list of job or calc names.
    :returns: A list of Job or Calc instances.
    """
    jobs = []
    for job_name in job_names:
        jobs.append(_get_job_or_calc(job_name))

    return jobs


def _get_job_or_calc(name):
    """
    Given a job or calc name, return the job or calc instance.

    :param name: The name if a job or calc.
    :returns: A list of Job or Calc instance.
    """
    job = None
    try:
        job = CALCS[name]
    except KeyError:
        try:
            job = JOBS[name]
        except KeyError:
            check_1st_level_keys(name)
    return job


def check_1st_level_keys(bad_name):
    """
    Give an informative error if a calc name is wrong.

    :param bad_name: A job name that can not be resolved.
    :raises: RuntimeError
    """

    # Check that it is bad.
    assert bad_name not in SPELLCHECK.base_words

    meantkey = SPELLCHECK.correct(bad_name)
    msg = '\nInvalid key in config file; %s \n' % bad_name
    if meantkey == bad_name:
        # There was no suggested word
        raise RuntimeError(msg)
    else:
        msg += 'Did you mean; %s?' % meantkey
        raise RuntimeError(msg)


def validate_job_instance(job_inst, atts):
    """
    Check the job instance for various errors.

    :param job_inst: A reference to the job function.
    :param atts: The function attributes from config.
    """
    check_files_to_load(atts)
    check_attributes(job_inst, atts)


def file_can_open(file2load):
    """
    Check if a file can be opened.
    :param file2load: file.
    :returns: True if file2load can be opened.
    """
    try:
        with open(file2load) as _:
            pass
    except IOError:
        return False
    return True


def check_files_to_load(atts):
    """
    Check the context, based on config attributes.

    This function relies on some assumptions.
    All jobs/calcs that load files label the files as;
       file_name OR
       file_list - for a list of files or a file

    :param atts: The function attributes from config.
    :raises: True for testing or RuntimeError
    """
    bad_file = []
    for key, value in atts.iteritems():
        if isinstance(value, dict) and 'save' not in key:
            if 'file_name' in value:
                file2load = value['file_name']
                if not file_can_open(file2load):
                    bad_file.append(file2load)
            elif 'file_list' in value:
                files2load = value['file_list']
                if isinstance(files2load, basestring):
                    files2load = [files2load]
                for file2load in files2load:
                    if not file_can_open(file2load):
                        bad_file.append(file2load)
    if len(bad_file) == 1:
        raise RuntimeError(
            'Invalid file name, %s in config file.' % bad_file[0])
    return True  # for testing


def check_attributes(job_calc_function, config_args):
    """
    Check the attributes of the jobs/cal functions for spelling.
    It will check if all attributes are
    * Missing when they are mandatory
    * typo args

    :param job_calc_function: A reference to the job function.
    :param config_args: The function attributes from config
    :raises: RuntimeError
    """
    unchecked_config_args = copy.copy(config_args)
    args, defaults = job_calc_function.get_required_args_no_context()
    name = job_calc_function.call_funct

    # Make sure the mandatory args are there
    # And remove them from the unchecked list
    for arg_call in args:
        try:
            del unchecked_config_args[arg_call]
        except KeyError:
            # An argument that must be present was not present.
            msg = 'The job %s is missing the parameter %s' % (name,
                                                              arg_call)
            raise RuntimeError(msg)

    # remove default parameters from the unchecked list
    for default_call in defaults:
        try:
            del unchecked_config_args[default_call]
        except KeyError:
            pass

    # If the are still unchecked args then there is an error
    if len(unchecked_config_args) > 0:
        msg = 'The job %s has the following unkown parameters;\n' % name
        for unknown_arg in unchecked_config_args:
            msg += '%s\n' % unknown_arg
        raise RuntimeError(msg)

    # For testing
    return True


READERS = {DEFAULT: _reader2,
           WINDV3: _wind_v3_reader,
           FLOODFABRICV2: _flood_fabric_v2_reader}
