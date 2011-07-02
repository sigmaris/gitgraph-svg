function getTreeJSON(node, result) {
  if(node == -1) {
    result(gitgraph.initial_tree)
  }
}

function setupDraggables() {
  $('#left_divider').draggable({
    axis: 'x',
    containment: 'parent',
    stop: function(event, ui) {
      var docWidth = $(document).width();
      var leftPercent = ui.offset.left / docWidth;
      var rightPercent = 1 - leftPercent;
      rightPercent -= 0.003; //allow for divider width
      $('#left_tree').css('width',100*leftPercent+'%');
      $('#right_container').css('width',100*rightPercent+'%');
      $('#left_divider').css('left','');
    }
  });
  
  $('#mid_divider').draggable({
    axis: 'y',
    containment: 'parent',
    stop: function(event, ui) {
      var docHeight = $(document).height();
      var topPercent = ui.offset.top / docHeight;
      var bottomPercent = 1 - topPercent;
      bottomPercent -= 0.003; //allow for divider width
      $('#top_graph').css('height',100*topPercent+'%');
      $('#bottom_pane').css('height',100*bottomPercent+'%');
      $('#mid_divider').css('top','');
    }
  });
}

$(document).ajaxStart(function() {
  gitgraph.loaderTimeout = setTimeout("$('.loader').show();", 100);
});

$(document).ajaxStop(function() {
  $('.loader').hide();
  if(gitgraph.loaderTimeout) {
    clearTimeout(gitgraph.loaderTimeout);
    delete gitgraph.loaderTimeout;
  }
});


$(document).ready(function() {
  
  $.ajaxSetup({
    traditional: true
  });
    
  $('#left_tree').jstree({
    "themes" : { "theme": "default", "url" : "/static/themes/default/style.css" },
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
            if(textStatus == 'success' || textstatus == 'notmodified') {
              $('#filename_' + sha_to_load).text(li_element.data('full_name'));
            }
          });
        }
      }
    }
  });
  
  setupDraggables();
  
  $('#reveal').click(function(event) {
    $('#reveal_ajax').load('/graph/'+gitgraph.loaded_count, $.param({branches: gitgraph.existing_branches}, true));
  })
});