from pyramid.view import view_config

import os
import random
import re
import json
from collections import namedtuple

from sqlalchemy.orm import joinedload


from externals.lib.misc import backup

from ..model              import DBSession
from ..model.model_tracks import Track

from . import web, action_ok, action_error, cache, generate_cache_key, comunity_only


from ..scripts.import_tracks import import_json_data as import_track
from ..views.tracks import invalidate_track

import logging
log = logging.getLogger(__name__)


ProviderToken = namedtuple('ProviderToken', ['provider', 'token'])

#-------------------------------------------------------------------------------
# Cache Management
#-------------------------------------------------------------------------------
LIST_CACHE_KEY = 'comunity_list'

list_version = random.randint(0,2000000000)
def invalidate_list_cache(request=None):
    global list_version
    list_version += 1
    cache.delete(LIST_CACHE_KEY)

def _generate_cache_key(request):
    global list_version
    return '-'.join([generate_cache_key(request), str(list_version)])

#-------------------------------------------------------------------------------
# Community Utils
#-------------------------------------------------------------------------------

class ComunityTrack():
    def __init__(self, request, track_id):
        assert track_id and track_id != 'undefined', 'track_id required'
        self.media_path = request.registry.settings['static.media']
        self.track_id = track_id
        self._track_dict = None
        self._import_required = False
    
    @property
    def track(self):
        if not self._track_dict:
            self._track_dict = DBSession.query(Track) \
                .options( \
                    joinedload(Track.tags), \
                    joinedload(Track.attachments), \
                    joinedload('tags.parent'), \
                    joinedload('lyrics'), \
                ) \
                .get(self.track_id).to_dict('full')
        return self._track_dict
    
    def import_track(self):
        with open(self.path_description_filename, 'r') as filehandle:
            import_track(filehandle, self.path_description_filename)
            invalidate_track(self.track_id)
    
    @property
    def path(self):
        return os.path.join(self.media_path, self.track['source_filename'])
    @property
    def path_backup(self):
        return os.path.join(self.path, '_old_versions')
    @property
    def path_source(self):
        return os.path.join(self.path, 'source')
    @property
    def path_description_filename(self):
        return os.path.join(self.path, 'description.json')
    @property
    def tag_data_filename(self):
        return os.path.join(self.path, 'tags.txt')
    @property
    def tag_data_raw(self):
        with open(self.tag_data_filename ,'r') as tag_data_filehandle:
            return tag_data_filehandle.read()
    @tag_data_raw.setter
    def tag_data_raw(self, tag_data):
        backup(self.tag_data_filename, self.path_backup)
        with open(self.tag_data_filename ,'w') as filehandle:
            filehandle.write(tag_data)
            self._import_required = True
    @property
    def tag_data(self):
        return {tuple(line.split(':')) for line in self.tag_data_raw.split('\n')}
    @property
    def source_data_filename(self):
        return os.path.join(self.path, 'sources.json')
    @property
    def source_data(self):
        with open(self.source_data_filename ,'r') as source_data_filehandle:
            return json.load(source_data_filehandle)
    @property
    def subtitle_filenames(self):
        return [k for k in self.source_data.keys() if re.match(r'^.*\.(ssa|srt)$', k)]
    @property
    def subtitle_data(self):
        def subtitles_read(subtitle_filename):
            with open(os.path.join(self.path_source, subtitle_filename) ,'r') as subtitle_filehandle:
                return subtitle_filehandle.read()
        return dict(((subtitle_filename, subtitles_read(subtitle_filename)) for subtitle_filename in self.subtitle_filenames))
    @subtitle_data.setter
    def subtitle_data(self, subtitle_data):
        for subtitle_filename, subtitle_data_raw in subtitle_data:
            subtitle_path_filename = os.path.join(self.path_source, subtitle_filename)
            backup(subtitle_path_filename, self.path_backup)
            with open(subtitle_path_filename, 'w') as filehandle:
                filehandle.write(subtitle_data_raw)
                self._import_required = True


#-------------------------------------------------------------------------------
# Community Views
#-------------------------------------------------------------------------------

@view_config(route_name='comunity')
@web
def comunity(request):
    return action_ok()

@view_config(route_name='comunity_upload')
@web
def comunity_upload(request):
    return action_ok()


@view_config(route_name='comunity_list')
@web
@comunity_only
def comunity_list(request):

    def _comnunity_list():
        # Get tracks from db
        tracks = [
            track.to_dict('full', exclude_fields=('lyrics','attachments','image')) \
            for track in DBSession.query(Track) \
                .order_by(Track.source_filename) \
                .options( \
                    joinedload(Track.tags), \
                    #joinedload(Track.attachments), \
                    joinedload('tags.parent'), \
                    #joinedload('lyrics'), \
                )
        ]
        
        # Get track folders from media source
        media_path = request.registry.settings['static.media']
        media_folders = set((folder for folder in os.listdir(media_path) if os.path.isdir(os.path.join(media_path, folder))))
        
        # Compare folder sets to identify unimported/renamed files
        track_folders = set((track['source_filename'] for track in tracks))
        not_imported = media_folders.difference(track_folders)
        missing_source = track_folders.difference(media_folders)
        
        return {
            'tracks': tracks,
            'not_imported': sorted(not_imported),
            'missing_source': sorted(missing_source),
        }

    data_tracks = cache.get_or_create(LIST_CACHE_KEY, _comnunity_list)
    return action_ok(data=data_tracks)


@view_config(route_name='comunity_track', request_method='GET')
@web
@comunity_only
def comunity_track(request):
    ctrack = ComunityTrack(request, request.matchdict['id'])
    return action_ok(data={
        'track': ctrack.track,
        'tag_matrix': {},
        'tag_data': ctrack.tag_data_raw,
        'subtitles': ctrack.subtitle_data,
    })

@view_config(route_name='comunity_track', request_method='POST')
@web
@comunity_only
def comunity_track_update(request):
    ctrack = ComunityTrack(request, request.matchdict['id'])
    # Save tag data
    if 'tag_data' in request.params:
        ctrack.tag_data_raw = request.params['tag_data']
    
    # rebuild subtitle_data dict
    subtitle_data = {(k.replace('subtitles_', ''), v) for k, v in request.params.items() if k.startswith('subtitles_')}
    if subtitle_data:
        ctrack.subtitle_data = subtitle_data
    
    if ctrack._import_required:
        ctrack.import_track()
    
    #import pdb ; pdb.set_trace()
    return action_ok()