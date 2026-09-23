angular.module('easymcfApp').directive('mcfLink', ['McfConnect', function (McfConnect) {
  return {
    restrict: 'A',
    link: function (scope, element) {
      function openAuthenticated(event) {
        var url = element.attr('href');
        if (!McfConnect.shouldOpenAuthenticated(url)) { return; }
        event.preventDefault();
        scope.$evalAsync(function () { McfConnect.openUrl(url); });
      }
      element.on('click', openAuthenticated);
      scope.$on('$destroy', function () { element.off('click', openAuthenticated); });
    }
  };
}]);