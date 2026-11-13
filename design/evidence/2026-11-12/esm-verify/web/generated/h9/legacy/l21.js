window.__esmOrder.push('l21');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['21'] = { id: 21, name: 'state-21' };
  window.__legacyLayers.view['21'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['21'].id; }
  };
  window.__legacyLayers.controller['21'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['21'].id,
        card: window.__legacyLayers.view['21'].render(),
        label: 'controller-21'
      };
    }
  };
})();
