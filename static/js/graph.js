function highlight(event, ids, colour) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery); 
  var svg = jQ(event.target).parents('svg');
  for(var index in ids) {
    jQ('#' + ids[index], svg).attr('fill', colour);
    jQ('.parent_' + ids[index],svg).addClass('highlight');
  }
}

function unhighlight(event, ids) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery); 
  var svg = jQ(event.target).parents('svg'); 
  for(var index in ids) {
    jQ('#' + ids[index], svg).attr('fill', 'white');
    jQ('.parent_' + ids[index],svg).removeClass('highlight');
  }
}

function load_commit(sha) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery);
  if(gitgraph.loaderTimeout) {
    if(console) {
      console.log("Busy loading another commit...");
    }
  } else {
    jQ('#bottom_pane').load('/sha/' + sha);
  }
}
