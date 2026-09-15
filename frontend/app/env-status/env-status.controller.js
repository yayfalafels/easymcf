// ENV-SETUP-06 — milestone 07's bootstrap shell screen. Static text only;
// deliberately does not call GET /api/v1/health (API-EP-07 reserves that
// endpoint for the test harness's own readiness poll).
angular.module('easymcfApp').controller('EnvStatusCtrl', function () {
  // nothing to compute — the template is static text (ENV-SETUP-06).
});
