// the QR/confirmation pop-up (17.IS.07: a pop-up, not a separate page), opened from the single nav icon.
// User-closable X; self-closes once the attempt reaches 'connected'. Shows only the current session state
// when nothing is in flight (17.IS.08: no attempt history) — Connect MCF only when not already valid
// (17.IS.09: a valid session hides the login action entirely, offering Disconnect instead).
angular.module('easymcfApp').directive('mcfConnectModal', ['McfConnect', function (McfConnect) {
  return {
    restrict: 'E',
    scope: {},
    link: function (scope) { scope.connect = McfConnect; },
    template:
      '<div class="modal mcf-modal" ng-if="connect.state.open" data-testid="mcf-connect-modal">' +
      '<button type="button" class="modal-close" ng-click="connect.close()" data-testid="mcf-modal-close" aria-label="Close">&times;</button>' +
      '<h2>MCF connection</h2>' +

      '<div ng-if="connect.isActive(connect.state.attempt) && (connect.state.attempt.status === \'starting\' || connect.state.attempt.status === \'verifying\')" data-testid="mcf-waiting">' +
      '<p>Starting the connection&hellip;</p></div>' +

      '<div ng-if="connect.state.attempt.status === \'awaiting_approval\'" data-testid="mcf-qr-step">' +
      '<p>Scan this with the Singpass app on your phone.</p>' +
      '<img ng-src="{{ connect.state.qrUrl }}" class="mcf-qr" data-testid="mcf-qr-image" alt="Singpass QR code">' +
      '<p ng-if="connect.state.qrLink"><a ng-href="{{ connect.state.qrLink }}" target="_blank" rel="noopener" data-testid="mcf-qr-link">Open Singpass</a></p>' +
      '<button class="secondary" ng-click="connect.cancelAttempt()" data-testid="mcf-cancel-attempt">Cancel</button>' +
      '</div>' +

      '<div ng-if="connect.state.attempt.status === \'account_confirmation_required\'" data-testid="mcf-confirm-step">' +
      '<p data-testid="mcf-confirm-message">Confirm you are MCF user {{ connect.state.attempt.account_email }}</p>' +
      '<button ng-click="connect.confirm(true)" data-testid="mcf-confirm-yes">Confirm</button>' +
      '<button class="secondary" ng-click="connect.confirm(false)" data-testid="mcf-confirm-no">Reject</button>' +
      '</div>' +

      '<div ng-if="connect.state.attempt.status === \'interaction_required\'" data-testid="mcf-mismatch-step">' +
      '<p data-testid="mcf-mismatch-message">Found MCF account {{ connect.state.attempt.account_email }}, ' +
      'already connected under a different account. Start a fresh connection attempt once that is sorted out.</p>' +
      '<button class="secondary" ng-click="connect.confirm(false)" data-testid="mcf-mismatch-dismiss">Dismiss</button>' +
      '</div>' +

      '<div ng-if="connect.state.attempt.status === \'failed\'" data-testid="mcf-authentication-failed">' +
      '<p data-testid="mcf-authentication-failed-message">Singpass authentication failed. Try again or cancel this connection.</p>' +
      '<button ng-click="connect.startAttempt()" data-testid="mcf-authentication-retry">Retry</button>' +
      '<button class="secondary" ng-click="connect.close()" data-testid="mcf-authentication-cancel">Cancel</button>' +
      '</div>' +

      '<div ng-if="!connect.isActive(connect.state.attempt) && (!connect.state.attempt || (connect.state.attempt.status !== \'interaction_required\' && connect.state.attempt.status !== \'failed\'))" data-testid="mcf-current-state">' +
      '<p data-testid="mcf-status">' +
      '<span ng-if="connect.state.session.status === \'valid\'">Connected as {{ connect.state.session.confirmed_account_email }}</span>' +
      '<span ng-if="connect.state.session.status !== \'valid\'">Not connected' +
      '<span ng-if="connect.state.attempt.status === \'expired\'"> — the last QR expired before it was scanned</span>' +
      '<span ng-if="connect.state.attempt.status === \'failed\'"> — the last attempt failed</span>' +
      '</span></p>' +
      '<button ng-if="connect.state.session.status === \'valid\'" ng-click="connect.openUrl(\'https://www.mycareersfuture.gov.sg/\')" data-testid="mcf-open">Open</button>' +
      '<button ng-if="connect.state.session.status === \'valid\'" ng-click="connect.disconnect()" data-testid="mcf-disconnect">Disconnect</button>' +
      '<button ng-if="connect.state.session.status !== \'valid\'" ng-click="connect.startAttempt()" data-testid="mcf-connect">Connect MCF</button>' +
      '</div>' +

      '<span ng-if="connect.state.error" class="field-error" data-testid="mcf-error">{{ connect.state.error }}</span>' +
      '</div>'
  };
}]);
