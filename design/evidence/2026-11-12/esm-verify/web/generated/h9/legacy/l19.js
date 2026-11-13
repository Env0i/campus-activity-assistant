window.__esmOrder.push('l19');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['19'] = { id: 19, name: 'state-19' };
  window.__legacyLayers.view['19'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['19'].id; }
  };
  window.__legacyLayers.controller['19'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['19'].id,
        card: window.__legacyLayers.view['19'].render(),
        label: 'controller-19'
      };
    }
  };
})();
