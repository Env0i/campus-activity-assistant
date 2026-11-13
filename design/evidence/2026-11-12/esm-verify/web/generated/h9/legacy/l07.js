window.__esmOrder.push('l07');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['07'] = { id: 7, name: 'state-07' };
  window.__legacyLayers.view['07'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['07'].id; }
  };
  window.__legacyLayers.controller['07'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['07'].id,
        card: window.__legacyLayers.view['07'].render(),
        label: 'controller-07'
      };
    }
  };
})();
