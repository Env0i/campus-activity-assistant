window.__esmOrder.push('l24');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['24'] = { id: 24, name: 'state-24' };
  window.__legacyLayers.view['24'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['24'].id; }
  };
  window.__legacyLayers.controller['24'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['24'].id,
        card: window.__legacyLayers.view['24'].render(),
        label: 'controller-24'
      };
    }
  };
})();
