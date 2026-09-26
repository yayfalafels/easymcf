angular.module('easymcfApp').factory('ConfirmDialog', ['$q', function ($q) {
  var pending = null;
  var state = { open: false, message: '', confirmLabel: 'Confirm' };

  return {
    state: state,
    ask: function (options) {
      pending = $q.defer();
      state.open = true;
      state.message = options.message;
      state.confirmLabel = options.confirmLabel || 'Confirm';
      return pending.promise;
    },
    answer: function (confirmed) {
      state.open = false;
      if (confirmed) { pending.resolve(); } else { pending.reject(); }
    }
  };
}]);
