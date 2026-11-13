window.__esmOrder.push('l11');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['11'] = { id: 11, name: 'state-11' };
  window.__legacyLayers.view['11'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['11'].id; }
  };
  window.__legacyLayers.controller['11'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['11'].id,
        card: window.__legacyLayers.view['11'].render(),
        label: 'controller-11'
      };
    }
  };
})();
