window.__esmOrder.push('l12');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['12'] = { id: 12, name: 'state-12' };
  window.__legacyLayers.view['12'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['12'].id; }
  };
  window.__legacyLayers.controller['12'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['12'].id,
        card: window.__legacyLayers.view['12'].render(),
        label: 'controller-12'
      };
    }
  };
})();
