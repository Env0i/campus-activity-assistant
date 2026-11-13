window.__esmOrder.push('l36');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['36'] = { id: 36, name: 'state-36' };
  window.__legacyLayers.view['36'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['36'].id; }
  };
  window.__legacyLayers.controller['36'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['36'].id,
        card: window.__legacyLayers.view['36'].render(),
        label: 'controller-36'
      };
    }
  };
})();
