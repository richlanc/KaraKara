
from libs.misc import postmortem, fast_scan, epoc
from processmedia_libs import add_default_argparse_args

from processmedia_libs.meta_manager import MetaManager
from processmedia_libs.processed_files_manager import ProcessedFilesManager
from processmedia_libs import subtitle_processor

from model.model_tracks import Track, Tag, Attachment, Lyrics, _attachment_types
from model import init_DBSession, DBSession, commit
from model.actions import get_tag, clear_all_tracks, last_update


import logging
log = logging.getLogger(__name__)


def main(**kwargs):
    """
     - hash and identify primary key for track
     - import tags
     - import subtiles
     - cleanup db - any sources we don't have the actual processed files for - prune and remove from db
       - check this removes unnneeded attachments
    """
    meta = MetaManager(kwargs['path_meta'])
    meta.load_all(mtime=epoc(last_update()))

    import pdb ; pdb.set_trace()
    pass


class TrackImporter(object):

    def __init__(self, meta_manager=None, path_meta=None, path_processed=None, **kwargs):
        self.meta = meta_manager or MetaManager(path_meta)
        self.processed_files_manager = ProcessedFilesManager(path_processed)

    def import_track(self, name):
        pass


# Arguments --------------------------------------------------------------------

def get_args():
    """
    Command line argument handling
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description="""processmedia2 importer
        """,
        epilog="""
        """
    )

    add_default_argparse_args(parser)

    parser.add_argument('--config_uri', action='store', help='', default='development.ini')

    args = vars(parser.parse_args())

    return args


if __name__ == "__main__":
    args = get_args()

    from pyramid.paster import get_appsettings
    logging.basicConfig(level=args['log_level'])
    settings = get_appsettings(args['config_uri'])
    init_DBSession(settings)

    postmortem(main, **args)