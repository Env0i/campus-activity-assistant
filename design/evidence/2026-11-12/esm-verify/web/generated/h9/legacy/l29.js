window.__esmOrder.push('l29');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['29'] = { id: 29, name: 'state-29' };
  window.__legacyLayers.view['29'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['29'].id; }
  };
  window.__legacyLayers.controller['29'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['29'].id,
        card: window.__legacyLayers.view['29'].render(),
        label: 'controller-29'
      };
    }
  };
})();
