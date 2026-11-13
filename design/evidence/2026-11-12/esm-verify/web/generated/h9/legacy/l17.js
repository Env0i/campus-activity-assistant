window.__esmOrder.push('l17');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['17'] = { id: 17, name: 'state-17' };
  window.__legacyLayers.view['17'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['17'].id; }
  };
  window.__legacyLayers.controller['17'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['17'].id,
        card: window.__legacyLayers.view['17'].render(),
        label: 'controller-17'
      };
    }
  };
})();
