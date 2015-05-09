import os
import cPickle
import logging

CACHE_FILE = 'wpa.cache'


def clear_cache(directory):
    cache_file = os.path.join(directory, CACHE_FILE)
    if os.path.exists(cache_file):
        os.unlink(cache_file)


def save_cache(directory, pid, data):
    logging.debug('Saving data to cache')
    cache_file = os.path.join(directory, CACHE_FILE)

    # First we load any data that might be already there:
    try:
        saved_data = cPickle.load(file(cache_file))
    except:
        saved_data = {}

    # Now we save the new data
    saved_data[pid] = data
    cPickle.dump(saved_data, file(cache_file, 'w'))


def get_from_cache(directory, pid, section):
    cache_file = os.path.join(directory, CACHE_FILE)

    try:
        data = cPickle.load(file(cache_file))
    except IOError:
        logging.debug('No cache file found')
        return None
    except ValueError:
        logging.debug('Invalid JSON in cache')
        return None

    data = data[pid]

    for i_section, section_data in data:
        if section == i_section:
            logging.debug('Getting section "%s" from cache' % section)
            return section_data

    logging.debug('No cache found for section: "%s"' % section)
    return None