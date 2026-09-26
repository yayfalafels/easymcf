angular.module('easymcfApp').directive('navBar', ['ErrorService', 'AuthService', 'RunPoller', function (ErrorService, AuthService, RunPoller) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.toasts = ErrorService.toasts; scope.auth = AuthService; scope.runPoller = RunPoller; },
    template:
      '<nav data-testid="nav-bar">' +
      '<a ng-if="auth.state.user" href="/tracks" data-testid="nav-tracks">Tracks</a> ' +
      '<a ng-if="auth.state.user" href="/posts" data-testid="nav-posts">Posts</a> ' +
      '<a ng-if="auth.state.user" href="/leads" data-testid="nav-leads">Leads</a> ' +
      '<a ng-if="auth.state.user" href="/offers" data-testid="nav-offers">Offers</a> ' +
      '<a ng-if="auth.state.user" href="/applications" data-testid="nav-applications">Applications</a> ' +
      '<a ng-if="auth.state.user" href="/automation" data-testid="nav-automation">Automation' +
      '<span ng-if="runPoller.isActive()" class="run-badge" data-testid="run-in-progress-badge" title="A run is in progress">●</span></a>' +
      '<mcf-nav-icon ng-if="auth.state.user"></mcf-nav-icon>' +
      '<user-menu></user-menu></nav>' +
      '<div data-testid="toasts"><div ng-repeat="t in toasts" data-testid="error-toast">{{t.text}}</div></div>'
  };
}]);
