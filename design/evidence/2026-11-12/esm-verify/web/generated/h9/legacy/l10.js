window.__esmOrder.push('l10');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['10'] = { id: 10, name: 'state-10' };
  window.__legacyLayers.view['10'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['10'].id; }
  };
  window.__legacyLayers.controller['10'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['10'].id,
        card: window.__legacyLayers.view['10'].render(),
        label: 'controller-10'
      };
    }
  };
})();
