function highlight(sha) {
  $('.label').attr('fill','black');
  $('#label_'+sha+', #author_'+sha+', #date_'+sha).attr('fill','blue');
}

function scrollToCommit(sha) {
  var labelOnPage = $('#'+sha);
  if(
    labelOnPage.length > 0 &&
    (
      labelOnPage.position().top < 30 ||
      labelOnPage.position().top > ($('#top_graph').height() - 30)
    )
  ) {
    //Reveal commit on page
    $('#top_graph').animate({
      scrollTop: labelOnPage.position().top + 
        $('#top_graph').scrollTop() -
        $('#top_graph').height() / 2
    });
  }
}

function searchForCommit(sha) {
  var labelOnPage = $('#'+sha);
  if(labelOnPage.length > 0) {
    //Reveal commit on page
    scrollToCommit(sha)
    load_commit(sha);
  } else {
    //Try searching on the server in the rest of the branch
    $('#reveal_ajax').load(getHeadGraphURL(), $.param({
      offset: gitgraph.loaded_count,
      branches: gitgraph.existing_branches,
      search_commit: sha
    }, true));
  }
}

function load_commit(sha) {
  if(gitgraph.loaderTimeout) {
    if(console) {
      console.log("Busy loading another commit...");
    }
  } else {
    $('#bottom_pane').load('/sha/' + sha, '', function(responseText, textStatus, jqXHR) {
      if(textStatus == 'success' || textStatus == 'notmodified') {
        highlight(sha);
        scrollToCommit(sha);
        if(gitgraph.top_expanded) {
          toggleTopExpansion();
        }
      }
    });
  }
}

$(document).ready(function() {
  
  $('.label').live('click', function(event) {
    var elementId = $(event.target).attr('id');
    searchForCommit(elementId.substring(elementId.indexOf('_') + 1));
    
  }).live('mouseover', function(inEvent) {
    $(inEvent.target).css('text-decoration','underline');
    
  }).live('mouseout', function(outEvent) {
    $(outEvent.target).css('text-decoration','');
  });
  
  $('.node').live('click', function(event) {
    searchForCommit($(event.target).attr('id'));
  });
  
});