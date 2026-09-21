angular.module('easymcfApp').directive('navBar', ['ErrorService', function (ErrorService) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.toasts = ErrorService.toasts; },
    template:
      '<nav data-testid="nav-bar"><a href="/tracks" data-testid="nav-tracks">Tracks</a> ' +
      '<a href="/leads" data-testid="nav-leads">Leads</a> ' +
      '<a href="/offers" data-testid="nav-offers">Offers</a></nav>' +
      '<div data-testid="toasts"><div ng-repeat="t in toasts" data-testid="error-toast">{{t.text}}</div></div>'
  };
}]);
