window.__esmOrder.push('l30');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['30'] = { id: 30, name: 'state-30' };
  window.__legacyLayers.view['30'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['30'].id; }
  };
  window.__legacyLayers.controller['30'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['30'].id,
        card: window.__legacyLayers.view['30'].render(),
        label: 'controller-30'
      };
    }
  };
})();
