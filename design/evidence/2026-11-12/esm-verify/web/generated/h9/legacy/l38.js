window.__esmOrder.push('l38');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['38'] = { id: 38, name: 'state-38' };
  window.__legacyLayers.view['38'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['38'].id; }
  };
  window.__legacyLayers.controller['38'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['38'].id,
        card: window.__legacyLayers.view['38'].render(),
        label: 'controller-38'
      };
    }
  };
})();
