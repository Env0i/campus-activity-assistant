window.__esmOrder.push('l03');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['03'] = { id: 3, name: 'state-03' };
  window.__legacyLayers.view['03'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['03'].id; }
  };
  window.__legacyLayers.controller['03'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['03'].id,
        card: window.__legacyLayers.view['03'].render(),
        label: 'controller-03'
      };
    }
  };
})();
