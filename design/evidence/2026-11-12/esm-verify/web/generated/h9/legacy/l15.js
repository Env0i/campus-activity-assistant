window.__esmOrder.push('l15');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['15'] = { id: 15, name: 'state-15' };
  window.__legacyLayers.view['15'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['15'].id; }
  };
  window.__legacyLayers.controller['15'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['15'].id,
        card: window.__legacyLayers.view['15'].render(),
        label: 'controller-15'
      };
    }
  };
})();
