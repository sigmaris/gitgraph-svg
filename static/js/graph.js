function highlight(event, ids, colour) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery); 
  var svg = jQ(event.target).parents('svg');
  for(var index in ids) {
    jQ('#' + ids[index], svg).attr('fill', colour);
  }
}

function unhighlight(event, ids) {
  var jQ = (window.parent ? window.parent.jQuery : window.jQuery); 
  var svg = jQ(event.target).parents('svg'); 
  for(var index in ids) {
    jQ('#' + ids[index], svg).attr('fill', 'white');
  }
}
