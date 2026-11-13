window.__esmOrder.push('l13');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['13'] = { id: 13, name: 'state-13' };
  window.__legacyLayers.view['13'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['13'].id; }
  };
  window.__legacyLayers.controller['13'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['13'].id,
        card: window.__legacyLayers.view['13'].render(),
        label: 'controller-13'
      };
    }
  };
})();
