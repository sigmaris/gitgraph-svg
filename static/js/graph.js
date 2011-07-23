function highlight(sha) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery);
  jQ('.label').attr('fill','black');
  jQ('#label_'+sha+', #author_'+sha+', #date_'+sha).attr('fill','blue');
}

function load_commit(sha) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery);
  if(gitgraph.loaderTimeout) {
    if(console) {
      console.log("Busy loading another commit...");
    }
  } else {
    jQ('#bottom_pane').load('/sha/' + sha, '', function(responseText, textStatus, jqXHR) {
      if(textStatus == 'success' || textStatus == 'notmodified') {
        highlight(sha);
      }
    });
  }
}

var jQ = (window.parent ? window.parent.jQuery : window.jQuery);
jQ(document).ready(function() {
  
  jQ('.label').live('click', function(event) {
    var elementId = $(event.target).attr('id');
    load_commit(elementId.substring(elementId.indexOf('_') + 1));
    
  }).live('mouseover', function(inEvent) {
    $(inEvent.target).css('text-decoration','underline');
    
  }).live('mouseout', function(outEvent) {
    $(outEvent.target).css('text-decoration','');
  });
  
  jQ('.node').live('click', function(event) {
    load_commit($(event.target).attr('id'));
  });
  
});