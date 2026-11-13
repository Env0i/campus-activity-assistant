window.__esmOrder.push('l01');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['01'] = { id: 1, name: 'state-01' };
  window.__legacyLayers.view['01'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['01'].id; }
  };
  window.__legacyLayers.controller['01'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['01'].id,
        card: window.__legacyLayers.view['01'].render(),
        label: 'controller-01'
      };
    }
  };
})();
