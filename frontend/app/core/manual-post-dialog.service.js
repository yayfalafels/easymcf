// ManualPostDialog (10.EL.19, page 4 Manual Post Entry). Same open()/save()/cancel() shape
// as OfferDialog (frontend/app/core/offer-dialog.service.js) — state lives on the service so
// the manual-post-modal directive can bind to it directly.
angular.module('easymcfApp').factory('ManualPostDialog', ['$q', 'ApiClient', function ($q, ApiClient) {
  var pending = null;
  var state = {
    open: false, tracks: [], trackId: null, positionTitle: '', companyName: '',
    urlRef: '', salaryHigh: null, postedDate: null, error: null
  };

  function iso(value) {
    if (!value) { return null; }
    if (typeof value === 'string') { return value; }
    return value.getFullYear() + '-' + String(value.getMonth() + 1).padStart(2, '0') + '-' + String(value.getDate()).padStart(2, '0');
  }

  // Unlike ErrorService.fieldMessage (which only surfaces a message when the backend names a
  // `field`), page 4's own design requires every rejection this dialog can receive — a 409 for
  // a duplicate post, an archived/missing track, or a user with no active track, none of which
  // carry a `field` — to show its message inline in the dialog, not only as the global toast
  // ErrorService.report already raises for any non-401/non-field-400 response.
  function describe(response) {
    var data = response && response.data;
    if (!data) { return { message: 'Request failed.' }; }
    return { field: data.field || null, message: data.message || ('Request failed (' + response.status + ').') };
  }

  return {
    state: state,
    open: function (tracks) {
      pending = $q.defer();
      angular.extend(state, {
        open: true, tracks: tracks || [], trackId: tracks && tracks[0] ? tracks[0].id : null,
        positionTitle: '', companyName: '', urlRef: '', salaryHigh: null, postedDate: new Date(), error: null
      });
      return pending.promise;
    },
    save: function () {
      ApiClient.promoteManualPost({
        track_id: state.trackId, position_title: state.positionTitle, company_name: state.companyName,
        url_ref: state.urlRef || null, salary_high: state.salaryHigh || null, posted_date: iso(state.postedDate)
      }).then(
        function (result) { state.open = false; pending.resolve(result); },
        function (response) { state.error = describe(response); }
      );
    },
    cancel: function () { state.open = false; pending.reject(); }
  };
}]);
