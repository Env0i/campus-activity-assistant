window.__esmOrder.push('l18');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['18'] = { id: 18, name: 'state-18' };
  window.__legacyLayers.view['18'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['18'].id; }
  };
  window.__legacyLayers.controller['18'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['18'].id,
        card: window.__legacyLayers.view['18'].render(),
        label: 'controller-18'
      };
    }
  };
})();
