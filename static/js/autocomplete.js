(function($){

function AutoCompletePlugin(element, options) {
  this.settings = {
    minlength: 4
  };
  $.extend(this.settings, options);
  var that = this;

  $(element).data('AutoCompletePlugin', this).keyup(
    function(event){
      var currentValue = $(element).val();
      if(currentValue && currentValue.length >= that.settings.minlength && !that.timeout) {
        that.timeout = setTimeout(function(){
          $.get(that.settings.url, { q: currentValue }, function(data, textStatus, jqXHR) {
            that.timeout = false;
            // If current value is a prefix of the returned value...
            if(typeof data == 'string' && data.indexOf(currentValue) == 0) {
              $(element).val(data);
  						that.selectRange(currentValue.length,data.length);
            }
          });
        }, 100);
      }
    }
  );  
  
  this.selectRange = function(start, end) {
    if(element.setSelectionRange) {
      element.focus();
      element.setSelectionRange(start, end);
    } else if(element.createTextRange) {
      var range = element.createTextRange();
      range.collapse(true);
      range.moveEnd('character', end);
      range.moveStart('character', start);
      range.select();
    }
  };
  
}

//Text range selection helper
$.fn.simpleAutocomp = function(options) {
  return this.each(function(index, el) {
    new AutoCompletePlugin(el, options);
  });
}

})(jQuery);