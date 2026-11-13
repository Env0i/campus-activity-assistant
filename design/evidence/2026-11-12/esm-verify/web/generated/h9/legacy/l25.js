window.__esmOrder.push('l25');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['25'] = { id: 25, name: 'state-25' };
  window.__legacyLayers.view['25'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['25'].id; }
  };
  window.__legacyLayers.controller['25'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['25'].id,
        card: window.__legacyLayers.view['25'].render(),
        label: 'controller-25'
      };
    }
  };
})();
