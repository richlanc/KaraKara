var DEFAULT_PLAYLIST_UPDATE_TIME = 3; //Seconds to poll server
var DEFAULT_VIDEO_BACKGROUND_VOLUME = 0.2;

var settings = {};
var playlist = [];
var split_indexs = [];
var socket;

function setup_remote() {
	var socket = new WebSocket("ws://"+location.hostname+":"+settings['karakara.websocket.port']+"/");
	socket.onopen = function(){ // Authenicate client with session key on socket connect
		socket.send(document.cookie.match(/karakara_session=(.+?)(\;|\b)/)[1]);  // TODO - replace with use of settings['session_key']
	};
	function receive(msg) {
		var cmd = $.trim(msg.data);
		console.log('remote control: '+cmd);
		if (cmd in commands) {commands[cmd]();}
	};
	socket.onmessage = receive;
}

function get_video() {
	return $('#player').get(0) || {};
}

var commands = {
	'play': function(e) {
		console.log('#play');
		var video = get_video();
		video.loop = false;
		video.volume = 1.0;
		video.src = "/files/" + get_attachment(playlist[0].track, "video");
		video.webkitRequestFullScreen();
		video.load();
		video.play();
	},
	'pause': function(e) {
		var video = get_video();
		// get state
		// if playing
		//   video.pause()
		// else
		//   video.play()
	},
	'skip': function(e) {
		console.log('#skip');
		//e.preventDefault();
		get_video().webkitExitFullScreen();
		song_finished("skipped");
	},
	'ended': function(e) {
		console.log('#player:ended');
		get_video().webkitExitFullScreen();
		song_finished("played");
	}
};

function get_attachment(track, type) {
	for(var i=0; i<track.attachments.length; i++) {
		if(track.attachments[i].type == type) {
			return track.attachments[i].location;
		}
	}
	return "";
}

function song_finished(status) {
	console.log("song_finished");
	$.getJSON(
		"/queue", {
			"method": "put",
			"queue_item.id": playlist[0].id,
			"status": status,
			"uncache": new Date().getTime()
		},
		function(data) {
			update_playlist();
		}
	);
}

function update_playlist() {
	//console.log("update_playlist");
	function _sig(list) {
		var sig = "";
		for(var i=0; i<list.length; i++) {
			sig = sig + list[i].time_touched;
		}
		return sig;
	}

	$.getJSON("/queue", {}, function(data) {
		//console.log("update_playlist getJSON response");
		if(_sig(playlist) != _sig(data.data.queue)) {
			//console.log("update_playlist:updated");
			playlist     = data.data.queue;
			split_indexs = data.data.queue_split_indexs;
			render_playlist();
			prepare_next_song();
		}
	});
}



function render_playlist() {
	console.log("render_playlist");
	
	// Split playlist with split_index (if one is provided)
	var playlist_ordered;
	var playlist_obscured;
	if (split_indexs.length && playlist.length) {
		// TODO split_indexs[0] is short term until we can support multiple groups in template
		playlist_ordered  = playlist.slice(0,split_indexs[0]);
		playlist_obscured = playlist.slice(split_indexs[0]);
		randomize(playlist_obscured);
	}
	else {
		playlist_ordered  = playlist
		playlist_obscured = [];
	}
	
	// Render queue_item scaffold
	function render_queue_items(queue, renderer_queue_item) {
		var output_buffer = "";
		for(var i=0; i<queue.length; i++) {
			var queue_item = queue[i];
			var track = queue_item['track'];
			track.tags.get = function(tag){
				if (tag in this) {return this[tag];}
				return ""
			};
			output_buffer += "<li>\n"+renderer_queue_item(queue_item, track)+"</li>\n";
		}
		return output_buffer;
	}
	
	// Render Playlist Ordered
	var queue_html = render_queue_items(playlist_ordered, function(queue_item, track) {
		return "" +
			"<p class='title'>"     + track.tags.get("title")   + "</p>\n" +
			"<p class='from'>"      + track.tags.get("from")    + "</p>\n" +
			"<p class='performer'>" + queue_item.performer_name + "</p>\n" +
			"<p class='time'> "     + timedelta_str(queue_item.total_duration*1000) + "</p>\n";
	});
	$('#playlist').html("<ol>"+queue_html+"</ol>\n");
	
	// Render Playlist Obscured
	if (playlist_obscured.length) {
		$('#upLater').html('<h2>Later On</h2>');
	}
	var queue_html = render_queue_items(playlist_obscured, function(queue_item, track) {
		var buffer = "";
		buffer += track.tags.get("title");
		track.tags.get("from") ? buffer += " ("+track.tags.get("from")+")" : null;
		buffer += " - "+queue_item.performer_name+"\n";
		return buffer;
	});
	$('#playlist_obscured').html("<ul>"+queue_html+"</ul>");
}


function prepare_next_song() {
	if(playlist.length == 0) {
		$('title').html("Waiting for Songs");
		$('#title').html("Waiting for Songs");
	}
	else {
		var title = playlist[0].track.title;
		if($('title').html() != title) {
			console.log("Preparing next song");
			$('title').html(title);
			$('#title').html("<a href='"+"/files/" + get_attachment(playlist[0].track, "video")+"'>"+title+"</a>");
			var video = get_video();
			video.src = "/files/" + get_attachment(playlist[0].track, "preview");
			video.loop = true;
			video.volume = settings["karakara.player.video.preview_volume"];
			video.load();
			video.play();
		}
	}
}

$(document).ready(function() {
	update_playlist();
	
	$("#play").click(commands.play);
	$("#skip").click(commands.skip);
	$("#player").bind("ended", commands.ended);
	
	$.getJSON("/settings", {}, function(data) {
		console.log("/settings");
		settings = data.data.settings;
		
		// Identify player.js as admin with admin cookie
		if (!data.identity.admin) {
			$.getJSON("/admin", {}, function(data) {
				if (!data.identity.admin) {
					console.error("Unable to set player as admin. The player may not function correctly. Check that admin mode is not locked");
					alert("Unable to set Admin mode for player interface");
				}
			})
		}
		
		// Set update interval
		settings["karakara.player.queue.update_time"] = settings["karakara.player.queue.update_time"] || DEFAULT_PLAYLIST_UPDATE_TIME;
		settings['interval'] = setInterval(update_playlist, settings["karakara.player.queue.update_time"] * 1000);
		console.log('update_interval='+settings["karakara.player.queue.update_time"]);
		
		settings["karakara.player.video.preview_volume"] = settings["karakara.player.video.preview_volume"] || DEFAULT_VIDEO_BACKGROUND_VOLUME;
		
		setup_remote();
	});
	
});
