// the one MCF nav icon (17.IS.05: one icon, not a separate link plus a badge): the MCF magnifying-glass mark
// in its own burgundy (17.IS.06), a stoplight dot overlay for session status (17.IS.10), opening the
// connect pop-up on click — the icon's own only entry point, since there is no separate /mcf page (17.IS.07).
angular.module('easymcfApp').directive('mcfNavIcon', ['McfConnect', function (McfConnect) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.connect = McfConnect; McfConnect.ensurePolling(); },
    template:
      '<span class="mcf-nav-control">' +
      '<button type="button" class="mcf-nav-icon" ng-click="connect.togglePopup()" data-testid="mcf-nav-icon" aria-label="MCF connection status">' +
      '<img class="mcf-nav-image" src="/assets/mcf-icon-magnifying-glass.png" alt="">' +
      '</button>' +
      '<span class="mcf-status-dot mcf-status-{{ connect.statusLight() }}" data-testid="mcf-status-dot" aria-hidden="true"></span>' +
      '</span>'
  };
}]);
