window.__esmOrder.push('l32');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['32'] = { id: 32, name: 'state-32' };
  window.__legacyLayers.view['32'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['32'].id; }
  };
  window.__legacyLayers.controller['32'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['32'].id,
        card: window.__legacyLayers.view['32'].render(),
        label: 'controller-32'
      };
    }
  };
})();
