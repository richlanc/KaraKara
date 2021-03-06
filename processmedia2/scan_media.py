import re

from libs.misc import postmortem, file_extension_regex, fast_scan_regex_filter
from libs.file import FolderStructure
from clint.textui.progress import mill as terminal_mill

from processmedia_libs import add_default_argparse_args, ALL_EXTS
from processmedia_libs.scan import locate_primary_files, get_file_collection, PRIMARY_FILE_RANKED_EXTS
from processmedia_libs.meta_manager import MetaManager

import logging
log = logging.getLogger(__name__)


VERSION = '0.0.0'


# Protection for legacy processed files  (could be removed in once data fully migriated)
DEFAULT_IGNORE_FILE_REGEX = re.compile(r'0\.mp4|0_generic\.mp4|\.bak|^\.|^0_video\.|0_\d\.jpg')

IGNORE_SEARCH_EXTS_REGEX = file_extension_regex(('txt', ))


# Main -------------------------------------------------------------------------

def scan_media(**kwargs):
    """
    part 1 of 3 of the encoding system

    SCAN
        -Update Meta-
        Load meta
        validate source meta files
            check mtime (ok or->)
            check hash
            mark fail if needed
        scan source
            skip validated
            scan hash in attempt to match failed
        create meta stubs for new files
        remove old failed bits of meta

        -Add jobs-
            update tags
            extract lyrics
            check source->destination hashs and add to job list


    """
    meta = MetaManager(kwargs['path_meta'])
    meta.load_all()

    log.info('1.) Read file structure into memory')
    folder_structure = FolderStructure.factory(
        path=kwargs['path_source'],
        search_filter=fast_scan_regex_filter(
            file_regex=file_extension_regex(ALL_EXTS),
            ignore_regex=DEFAULT_IGNORE_FILE_REGEX,
        )
    )

    log.info('2.) Locate primary files')
    # Note: Duplicate media is completely ignored/removed in this list
    primary_files = locate_primary_files(folder_structure, file_regex=file_extension_regex(PRIMARY_FILE_RANKED_EXTS))

    log.info("3.) Find associated files as a 'file collection' (based on the name of the primary file)")
    file_collections = {
        f.file_no_ext: get_file_collection(folder_structure, f)
        for f in primary_files
    }

    log.info('4.) Associate file_collections with existing metadata objects')
    for name, file_collection in terminal_mill(file_collections.items()):
        meta.load(name)
        m = meta.get(name)
        for f in file_collection:
            m.associate_file(f)
        meta.save(name)

    log.info('5.) Attempt to find associate unassociated files but finding them on the folder_structure in memory')
    for m in meta.meta_with_unassociated_files:
        for filename, scan_data in m.unassociated_files.items():

            # 5a.) The unassociated file may not have been found in the inital collection scan,
            # check it's original location and associate if it exists
            f = folder_structure.get(scan_data.get('relative')) if scan_data.get('relative') else None
            if f:
                m.associate_file(f)
                log.warn('Associating found missing file %s to %s - this should not be a regular occurance, move/rename this so it is grouped effectivly', f.relative, m.name)
                continue

            # 5b.) Search the whole folder_structure in memory for a matching hash
            mtime = scan_data['mtime']
            for f in folder_structure.scan(
                lambda f:
                    not IGNORE_SEARCH_EXTS_REGEX.search(f.file)
                    and
                    (f.file == filename or f.stats.st_mtime == mtime)
                    and
                    str(f.hash) == scan_data['hash']
            ):
                log.warn('Associating found missing file %s to %s - this should not be a regular occurance, move/rename this so it is grouped effectivly', f.relative, m.name)
                m.associate_file(f)
                break

    log.info('6.) Remove unmatched meta entrys')
    # (If processed data already exisits, it will be relinked at the encode level)
    for name in [m.name for m in meta.unmatched_entrys]:
        log.info('Removing meta %s', m.name)
        meta.delete(m.name)

    meta.save_all()


# Arguments --------------------------------------------------------------------

def get_args():
    """
    Command line argument handling
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description="""processmedia
        """,
        epilog="""
        """
    )

    add_default_argparse_args(parser, version=VERSION)

    args = vars(parser.parse_args())

    return args


if __name__ == "__main__":
    args = get_args()
    logging.basicConfig(level=args['log_level'])

    postmortem(scan_media, **args)
