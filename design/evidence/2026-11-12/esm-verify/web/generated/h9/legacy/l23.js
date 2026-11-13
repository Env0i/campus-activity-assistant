window.__esmOrder.push('l23');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {
  window.__legacyLayers = window.__legacyLayers || { state: {}, view: {}, controller: {} };
  window.__legacyLayers.state['23'] = { id: 23, name: 'state-23' };
  window.__legacyLayers.view['23'] = {
    render: function () { return 'card-' + window.__legacyLayers.state['23'].id; }
  };
  window.__legacyLayers.controller['23'] = {
    build: function () {
      return {
        id: window.__legacyLayers.state['23'].id,
        card: window.__legacyLayers.view['23'].render(),
        label: 'controller-23'
      };
    }
  };
})();
