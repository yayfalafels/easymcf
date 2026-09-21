angular.module('easymcfApp').factory('OfferDialog', ['$q', 'ApiClient', 'ErrorService', function ($q, ApiClient, ErrorService) {
  var pending = null;
  var state = { open: false, leads: [], search: '', leadId: null, offerDate: null, amount: null, deadline: null, error: null };

  function iso(value) {
    if (!value) { return null; }
    if (typeof value === 'string') { return value; }
    return value.getFullYear() + '-' + String(value.getMonth() + 1).padStart(2, '0') + '-' + String(value.getDate()).padStart(2, '0');
  }
  function label(l) { return l.position_title + ' — ' + l.company_name; }
  function choose(id) {
    var lead = state.leads.filter(function (l) { return l.id === id; })[0];
    state.leadId = lead ? lead.id : null;
    state.amount = lead ? lead.expected_salary_sgd : null;
    state.deadline = lead && lead.deadline ? new Date(lead.deadline) : null;
  }

  return {
    state: state,
    label: label,
    matches: function () {
      var q = state.search.toLowerCase();
      return state.leads.filter(function (l) { return !q || label(l).toLowerCase().indexOf(q) !== -1; });
    },
    choose: function () { choose(state.leadId); },
    open: function (lead) {
      pending = $q.defer();
      state.open = true; state.search = ''; state.error = null; state.offerDate = new Date(); choose(null);
      ApiClient.list('lead', { stage: 'INTERVIEW', status: 'OPEN' }).then(function (rows) {
        state.leads = rows;
        if (lead) { choose(lead.id); }
      });
      return pending.promise;
    },
    save: function () {
      ApiClient.create('offer', { lead_id: state.leadId, offer_date: iso(state.offerDate), amount_sgd: state.amount, deadline: iso(state.deadline) })
        .then(function (offer) { state.open = false; pending.resolve(offer); },
              function (response) { state.error = ErrorService.fieldMessage(response); });
    },
    cancel: function () { state.open = false; pending.reject(); }
  };
}]);
