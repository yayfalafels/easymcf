// the mcf_attempt/mcf_session poll and the connect-popup state, opened from the single nav icon (17.IS.05/.06/.10).
angular.module('easymcfApp').factory('McfConnect', ['$interval', '$window', 'ApiClient', function ($interval, $window, ApiClient) {
  var POLL_MS = 3000;
  var ACTIVE = ['starting', 'awaiting_approval', 'verifying', 'account_confirmation_required'];
  var state = { open: false, attempt: null, session: null, qrUrl: null, qrLink: null, error: null };
  var pollTimer = null;

  function latestOf(rows) { return rows.length ? rows[rows.length - 1] : null; }
  function isActive(attempt) { return !!attempt && ACTIVE.indexOf(attempt.status) !== -1; }
  function hasValidSession() { return !!state.session && state.session.status === 'valid'; }
  function isMcfUrl(url) { return /^https:\/\/([a-z0-9-]+\.)*mycareersfuture\.gov\.sg(?:\/|$)/i.test(url || ''); }

  function refreshQr() {
    if (!state.attempt || state.attempt.status !== 'awaiting_approval') { state.qrUrl = null; state.qrLink = null; return; }
    state.qrUrl = ApiClient.mcfAttemptQrUrl(state.attempt.id) + '?t=' + Date.now();
    ApiClient.mcfAttemptQrLink(state.attempt.id).then(function (r) { state.qrLink = r.link; });
  }

  function refresh() {
    ApiClient.list('mcf_attempt', {}).then(function (rows) {
      state.attempt = latestOf(rows);
      if (isActive(state.attempt) && state.attempt.status === 'awaiting_approval') { refreshQr(); }
    });
    ApiClient.list('mcf_session', {}).then(function (rows) { state.session = rows.length ? rows[0] : null; });
  }

  return {
    state: state,
    isActive: isActive,
    hasValidSession: hasValidSession,
    shouldOpenAuthenticated: function (url) { return hasValidSession() && isMcfUrl(url); },
    openUrl: function (url) {
      if (!hasValidSession()) { $window.open(url, '_blank', 'noopener'); return; }
      return ApiClient.openMcfSession(url).then(function (result) {
        if (result.mode === 'redirect') { $window.open(result.url, '_blank', 'noopener'); }
      }, function () { $window.open(url, '_blank', 'noopener'); });
    },
    // 'green' (valid) | 'amber' (an attempt is in flight) | 'red' (missing or expired) — the nav icon's stoplight
    statusLight: function () {
      if (isActive(state.attempt)) { return 'amber'; }
      return state.session && state.session.status === 'valid' ? 'green' : 'red';
    },
    ensurePolling: function () {
      if (pollTimer) { return; }
      refresh();
      pollTimer = $interval(refresh, POLL_MS);
    },
    openPopup: function () { state.open = true; state.error = null; },
    togglePopup: function () { state.open = !state.open; state.error = null; },
    close: function () { state.open = false; },
    startAttempt: function () {
      state.error = null;
      ApiClient.startMcfAttempt().then(function (row) { state.attempt = row; refreshQr(); }, function (r) {
        state.error = (r.data && r.data.message) || 'Could not start the connection.';
      });
    },
    confirm: function (accept) {
      ApiClient.confirmMcfAttempt(state.attempt.id, accept).then(function (row) {
        state.attempt = row;
        refresh();   // state.session lags a full poll tick otherwise (17.IS.09's diagnostic)
      });
    },
    disconnect: function () {
      if (!state.session) { return; }
      var id = isActive(state.attempt) || (state.attempt && state.attempt.status === 'connected') ? state.attempt.id : null;
      if (!id) { return; }
      ApiClient.cancelMcfAttempt(id).then(function () { refresh(); });
    },
    cancelAttempt: function () {
      if (!isActive(state.attempt)) { return; }
      ApiClient.cancelMcfAttempt(state.attempt.id).then(function (row) {
        state.attempt = row;
        state.qrUrl = null;
        state.qrLink = null;
        refresh();
      });
    }
  };
}]);
