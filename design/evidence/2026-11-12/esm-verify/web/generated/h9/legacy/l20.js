window.__esmOrder.push('l20');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['20'] = { id: 20, name: 'state-20' };
  window.__legacyLayers.view['20'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['20'].id; }
  };
  window.__legacyLayers.controller['20'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['20'].id,
        card: window.__legacyLayers.view['20'].render(),
        label: 'controller-20'
      };
    }
  };
})();
