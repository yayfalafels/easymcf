angular.module('easymcfApp').directive('navBar', ['ErrorService', 'AuthService', function (ErrorService, AuthService) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.toasts = ErrorService.toasts; scope.auth = AuthService; },
    template:
      '<nav data-testid="nav-bar">' +
      '<a ng-if="auth.state.user" href="/tracks" data-testid="nav-tracks">Tracks</a> ' +
      '<a ng-if="auth.state.user" href="/posts" data-testid="nav-posts">Posts</a> ' +
      '<a ng-if="auth.state.user" href="/leads" data-testid="nav-leads">Leads</a> ' +
      '<a ng-if="auth.state.user" href="/offers" data-testid="nav-offers">Offers</a>' +
      '<mcf-nav-icon ng-if="auth.state.user"></mcf-nav-icon>' +
      '<user-menu></user-menu></nav>' +
      '<div data-testid="toasts"><div ng-repeat="t in toasts" data-testid="error-toast">{{t.text}}</div></div>'
  };
}]);
