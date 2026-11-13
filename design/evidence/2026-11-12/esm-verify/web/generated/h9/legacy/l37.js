window.__esmOrder.push('l37');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['37'] = { id: 37, name: 'state-37' };
  window.__legacyLayers.view['37'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['37'].id; }
  };
  window.__legacyLayers.controller['37'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['37'].id,
        card: window.__legacyLayers.view['37'].render(),
        label: 'controller-37'
      };
    }
  };
})();
