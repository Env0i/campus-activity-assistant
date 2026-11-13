window.__esmOrder.push('l06');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['06'] = { id: 6, name: 'state-06' };
  window.__legacyLayers.view['06'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['06'].id; }
  };
  window.__legacyLayers.controller['06'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['06'].id,
        card: window.__legacyLayers.view['06'].render(),
        label: 'controller-06'
      };
    }
  };
})();
