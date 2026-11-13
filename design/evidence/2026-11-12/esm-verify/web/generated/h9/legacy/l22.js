window.__esmOrder.push('l22');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['22'] = { id: 22, name: 'state-22' };
  window.__legacyLayers.view['22'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['22'].id; }
  };
  window.__legacyLayers.controller['22'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['22'].id,
        card: window.__legacyLayers.view['22'].render(),
        label: 'controller-22'
      };
    }
  };
})();
