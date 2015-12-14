import subprocess
import webbrowser
import argparse
import logging
import time
import sys
import os

from jinja2 import StrictUndefined, Environment
from collections import OrderedDict

from wpamod.utils.main_pid import get_main_pid
from wpamod.utils.log import configure_logging
from wpamod.utils.cache import save_cache, clear_cache, get_from_cache

from wpamod.plugins.meliae_basic import MeliaeBasic
from wpamod.plugins.meliae_largest import MeliaeLargestObject
from wpamod.plugins.meliae_usage_summary import MeliaeUsageSummary
from wpamod.plugins.sys_info import SystemInformation
from wpamod.plugins.cpu_usage import CPUUsageByFunction
from wpamod.plugins.psutil_summary import PSUtilSummary
from wpamod.plugins.core_status import CoreStatus
from wpamod.plugins.request_count import HTTPRequestCount
from wpamod.plugins.log_parser import LogParser

# Leave the plugins list in this format so it's easier to comment the plugins
# we don't need during development/testing
#
# We'll create an HTML report using all these plugins, note that this is
# different from `wpa` where the user can choose which plugins to run
PLUGINS = [
           MeliaeBasic,
           #MeliaeUsageSummary,
           MeliaeLargestObject,
           #CPUUsageByFunction,
           CoreStatus,
           PSUtilSummary,
           SystemInformation,
           HTTPRequestCount,
           LogParser
]

GRAPH_SECTION = ' - graph'


def main():
    args = parse_args()

    configure_logging(args.debug)
    logging.debug('Starting wpa-html')

    # Here we store the data to send to the HTML template
    collector_data = OrderedDict()

    for directory in args.directories:
        process_directory(args, directory, collector_data)

    # Render the HTML file using the context
    jinja2_env = Environment(undefined=StrictUndefined,
                             trim_blocks=True,
                             lstrip_blocks=True)
    jinja2_env.globals['max_items_count'] = max_items_count
    jinja2_env.globals['extract_partial_data'] = extract_partial_data

    template = file('wpamod/html_report/templates/report.html').read()
    template = jinja2_env.from_string(template)
    rendered_template = template.render(collector_data=collector_data)

    output = os.path.abspath(os.path.expanduser(args.output_file))
    file(output, 'w').write(rendered_template)

    # Open the file in a browser
    #webbrowser.open('file://%s' % output)
    #time.sleep(0.5)


def max_items_count(collector_data, plugin_name):
    """
    :param collector_data: The data generated using process_directory
    :param plugin_name: The name of the plugin
    :return: A list with the max number of items generated by the plugin for all
             the existing revisions under analysis.
    """
    max_items = -1

    for revision in collector_data:

        current_items = len(collector_data[revision][plugin_name])
        if current_items > max_items:
            max_items = current_items

    return range(max_items)


def extract_partial_data(collector_data, revision, plugin_name, data_name):
    """
    :param collector_data: The data generated using process_directory
    :param revision: The revision for which we need the data
    :param plugin_name: The name of the plugin
    :param data_name: The key name for the data inside the plugin
    :return: A list with the data
    """
    output = []

    for _id, data in collector_data[revision][plugin_name].iteritems():
        data_point = data[data_name] if data[data_name] is not None else 0
        output.append(data_point)

    return output


def get_revision_date(revision):
    """
    :param revision: The revision to check
    :return: The date for the w3af revision, n/a if the w3af directory does not
             exist in ../w3af/
    """
    get_date_cmd = 'git show -s --format=%%ci %s' % revision
    try:
        return subprocess.check_output(get_date_cmd,
                                       cwd=os.path.abspath('../w3af/'),
                                       shell=True).strip()
    except:
        logging.debug('Failed to retrieve the revision date. No w3af git'
                      ' repository found at ../w3af/')
        return 'n/a'


def process_directory(args, directory, collector_data):
    """
    Run all the plugins on a specific directory, with the user configuration
    and save the output to collector_data.

    :param args: User configuration
    :param directory: The directory which contains the data
    :param collector_data: Dict where the output should be written
    :return: None
    """
    try:
        config_version = os.path.join(directory, 'config', 'version')
        revision = file(config_version).read().strip()
    except IOError:
        msg = ('%s is not a valid collector output directory (config/version is'
               ' missing)')
        logging.error(msg % directory)
        sys.exit(-1)

    pargs = (directory, revision)
    logging.debug('Starting wpa-html analysis of %s (%s)' % pargs)

    if args.clear_cache:
        clear_cache(directory)

    try:
        rev_file = os.path.join(directory, 'config', 'collector.revision')
        collector_revision = file(rev_file).read().strip()
    except IOError:
        msg = ('%s is not a valid collector output directory (config/'
               'collector.revision is missing).')
        logging.error(msg % directory)
        sys.exit(-2)

    try:
        description_file = os.path.join(directory, 'config', 'description')
        description = file(description_file).read().strip()
    except IOError:
        msg = ('%s is not a valid collector output directory (config/'
               'description is missing).')
        logging.error(msg % directory)
        sys.exit(-3)

    #
    # Set unique revision id
    #
    i = -1

    while True:
        i += 1
        unique_revision = '%s-%s' % (revision, i)
        if unique_revision not in collector_data:
            collector_data[unique_revision] = {}
            break

    # Save the analysis meta-data
    meta_data = {'directory': directory,
                 'revision': revision,
                 'revision-date': get_revision_date(revision),
                 'collector-revision': collector_revision,
                 'description': description}

    collector_data[unique_revision]['meta-data'] = meta_data

    # Choose which PID to analyze
    pid = get_main_pid(directory)

    for plugin_klass in PLUGINS:
        plugin_inst = plugin_klass(directory, pid)
        name = plugin_inst.get_output_name()

        data = get_from_cache(directory, pid, name + GRAPH_SECTION)

        if data is None:
            data = plugin_inst.generate_graph_data()
            save_cache(directory, pid, name + GRAPH_SECTION, data)

        collector_data[unique_revision][name] = data


def parse_args():
    """
    return: A tuple with config_file, version.
    """
    parser = argparse.ArgumentParser(description='Analyze w3af performance'
                                                 ' data and generate HTML')
    parser.add_argument('directories', help='Input directories', nargs='+')
    parser.add_argument('--output-file', help='Output HTML file', required=True)
    parser.add_argument('--debug', action='store_true',
                        help='Print debugging information')
    parser.add_argument('--clear-cache', action='store_true',
                        help='Clear analysis cache for specified path')

    args = parser.parse_args()
    return args
