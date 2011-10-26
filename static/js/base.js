// http://www.quirksmode.org/js/cookies.html
function setCookie(name,value,days) {
  if (days) {
    var date = new Date();
    date.setTime(date.getTime()+(days*24*60*60*1000));
    var expires = "; expires="+date.toGMTString();
  }
  else var expires = "";
  document.cookie = name+"="+value+expires+"; path=/";
}

function getCookie(name) {
  var nameEQ = name + "=";
  var ca = document.cookie.split(';');
  for(var i=0;i < ca.length;i++) {
    var c = ca[i];
    while (c.charAt(0)==' ') c = c.substring(1,c.length);
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
  }
  return null;
}

function eraseCookie(name) {
  setCookie(name,"",-1);
}

function getTreeJSON(node, result) {
  if(node == -1) {
    result(gitgraph.initial_tree);
  } else {
    var sha = $(node).children('a').attr('href').substring(1);
    $.getJSON('/sha/' + sha, $.param({'parent_name': $(node).data('full_name')}), result);
  }
}

function setHorizDivider(topPercent) {
  var bottomPercent = 1 - topPercent;
  bottomPercent -= 0.004; //allow for divider width
  $('#top_graph').css('height',100*topPercent+'%');
  $('#bottom_pane').css('height',100*bottomPercent+'%');
  $('#mid_divider').css('top','');
}

function setVertDivider(leftPercent) {
  var rightPercent = 1 - leftPercent;
  rightPercent -= 0.003; //allow for divider width
  $('#left_tree').css('width',100*leftPercent+'%');
  $('#right_container').css('width',100*rightPercent+'%');
  $('#left_divider').css('left','');
}

function toggleTopExpansion(event) {
  if(!gitgraph.top_expanded) {
    gitgraph.top_expanded = true;
    gitgraph.old_top_height = $('#top_graph').css('height');
    gitgraph.old_bottom_height = $('#bottom_pane').css('height');
    $('#top_graph').animate({height: '99.6%'}, 'fast');
    $('#bottom_pane').animate({height: '0%'}, 'fast');
  } else {
    gitgraph.top_expanded = false;
    $('#top_graph').animate({height: gitgraph.old_top_height}, 'fast');
    $('#bottom_pane').animate({height: gitgraph.old_bottom_height}, 'fast');
  }
}

function toggleBottomExpansion(event) {
  if(!gitgraph.bottom_expanded) {
    gitgraph.bottom_expanded = true;
    gitgraph.old_top_height = $('#top_graph').css('height');
    gitgraph.old_bottom_height = $('#bottom_pane').css('height');
    $('#top_graph').animate({height: '0%'}, 'fast');
    $('#bottom_pane').animate({height: '99.6%'}, 'fast');
  } else {
    gitgraph.bottom_expanded = false;
    $('#top_graph').animate({height: gitgraph.old_top_height}, 'fast');
    $('#bottom_pane').animate({height: gitgraph.old_bottom_height}, 'fast');
  }
}

function setupDraggables() {
  $('#left_divider').draggable({
    axis: 'x',
    containment: 'parent',
    stop: function(event, ui) {
      var docWidth = $(document).width();
      //Constrain to 2% away from either edge
      var leftPercent = Math.min(Math.max(ui.offset.left / docWidth, 0.02),0.98);
      setCookie('leftPercent',leftPercent,30);
      setVertDivider(leftPercent);
    }
  });
  
  $('#mid_divider').draggable({
    axis: 'y',
    containment: 'parent',
    stop: function(event, ui) {
      gitgraph.top_expanded = false;
      gitgraph.bottom_expanded = false;
      var docHeight = $('#wrapper').height();
      //Constrain to 2% away from either edge
      var topPercent = Math.min(Math.max((ui.offset.top - $('#toolbar').height()) / docHeight,0.02),0.98);
      setCookie('topPercent',topPercent,30);
      setHorizDivider(topPercent);
    }
  });
  
  //Set the initial position from stored prefs
  var topPercent = getCookie('topPercent');
  if(topPercent) {
    setHorizDivider(topPercent);
  }
  var leftPercent = getCookie('leftPercent');
  if(leftPercent) {
    setVertDivider(leftPercent);
  }
  
  //Expand the top graph on double-click
  $('#top_graph').dblclick(toggleTopExpansion);
  
  //Expand the bottom pane on double-click
  $('#bottom_pane').dblclick(toggleBottomExpansion);
  
  //This doesn't work at the moment - why?
  $('#top_graph th').resizable({
    handles: 'all',
    maxHeight: 17,
    minHeight: 17
  });
}

$(document).ajaxStart(function() {
  gitgraph.loaderTimeout = setTimeout("$('.loader').show();", 200);
});

$(document).ajaxStop(function() {
  $('.loader').hide();
  if(gitgraph.loaderTimeout) {
    clearTimeout(gitgraph.loaderTimeout);
    delete gitgraph.loaderTimeout;
  }
});

function getHeadGraphURL() {
  if(gitgraph.current_ref) {
    return '/' + gitgraph.current_ref;
  } else if(gitgraph.current_head) {
    return '/graph/' + gitgraph.current_head;
  } else {
    return '/';
  }
}

$(document).ready(function() {
  
  $.ajaxSetup({
    traditional: true
  });
  
  $(document).ajaxError(function(event, jqXHR, settings, thrownError) {
    switch(jqXHR.status) {
      case 404:
        alert("The requested commit, tree or object could not be found.");
        break;
      default:
        alert("There was an error fetching data from " + settings.url + ":\n" + thrownError);
    }
  });
  
  $('#left_tree').jstree({
    "themes" : { "theme": "apple", "url" : "/static/themes/apple/style.css", dots: false },
    "json_data" : {
      "data" : getTreeJSON
    },
    "ui": {
      "select_limit": 1
    },
    "plugins" : [ "themes", "json_data", 'ui' ]
  }).bind('select_node.jstree',function(event, data) {
    if(data.args[2]) {
      var a_element = $(data.args[2].target);
      if(a_element.hasClass('file')) {
        //Try finding the content on the parent <li> element
        var li_element = a_element.parent();
        var diff_content = li_element.data('content');
        if(diff_content) {
          //Show content in pane
          $('#bottom_pane').html(diff_content);
        } else {
          //Load content via AJAX.. trim off the # from href
          var compare_to = li_element.data('old_sha');
          if(compare_to) {
            data = {compare_to: compare_to};
          } else {
            data = {};
          }
          var sha_to_load = a_element.attr('href').substring(1);
          $('#bottom_pane').load('/sha/' + sha_to_load, $.param(data), function(responseText, textStatus, jqXHR) {
            if(textStatus == 'success' || textStatus == 'notmodified') {
              $('#filename_' + sha_to_load).text(li_element.data('full_name')).append($('<a class="nav_link" href="#changed_line">(Go to first change)</a>'));
            }
          });
        }
      }
    }
  });
  
  setupDraggables();
  
  $('#reveal').click(function(event) {
    $('#reveal_ajax').load(getHeadGraphURL(), $.param({offset: gitgraph.loaded_count, branches: gitgraph.existing_branches}, true));
  });
  
  $('#current_commit_title').submit(function(event) {
    var inputSHA = $('#find_commit').val();
    if(/^[a-fA-F0-9]{40}$/.test(inputSHA)) {
      searchForCommit(inputSHA);
    } else {
      alert("That isn't a valid SHA ID.");
    }
    event.preventDefault();
    return false;
  });

  $('#ref_select').change(function() {
    window.location.href ='/'+$('#ref_select').val();
  })
  
  highlight(gitgraph.current_head);
});