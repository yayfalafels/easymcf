angular.module('easymcfApp').factory('ErrorService', ['$timeout', function ($timeout) {
  var toasts = [];

  function messageFor(r) {
    if (r.status <= 0) { return 'Cannot reach the backend.'; }
    if (r.data && r.data.message) { return r.data.message; }
    return 'Request failed (' + r.status + ').';
  }

  return {
    toasts: toasts,
    report: function (r, prefix) {
      if (r.status === 400 && r.data && r.data.field) { return; }
      var toast = { text: (prefix ? prefix + ': ' : '') + messageFor(r) };
      toasts.push(toast);
      $timeout(function () { toasts.splice(toasts.indexOf(toast), 1); }, 8000);
    },
    fieldMessage: function (r) {
      return r.data && r.data.field ? { field: r.data.field, message: r.data.message } : null;
    }
  };
}]);
