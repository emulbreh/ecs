ecs.dragdrop = {};

ecs.dragdrop.Frame = new Class({
    Implements: Events,
    initialize: function(el, options){
        this.element = $(el);
        options = options || {};
        this.paintOverlay = options.paintOverlay || true;
        this.mouseDownListener = this.onMouseDown.bind(this);
        this.mouseUpListener = this.onMouseUp.bind(this);
        this.mouseMoveListener = this.onMouseMove.bind(this);
        this.start = null;
        this.basePosition = null;
        this.point = null;
        this.frameOverlay = new Element('div', {'class': 'ecs-DragDropFrameOverlay'});
        this.attach();
    },
    attach: function(){
        this.element.addEvent('mousedown', this.mouseDownListener);
        this.element.addEvent('mouseup', this.mouseUpListener);
        this.element.addEvent('mousemove', this.mouseMoveListener);
    },
    detach: function(){
        this.element.removeEvent('mousedown', this.mouseDownListener);
        this.element.removeEvent('mouseup', this.mouseUpListener);
        this.element.removeEvent('mousemove', this.mouseMoveListener);
    },
    onMouseDown: function(e){
        this.basePosition = this.element.getPosition();
        this.start = e.page;
        this.element.grab(this.frameOverlay);
        this.onMouseMove(e);
    },
    onMouseUp: function(e){
        var frame = this.getFrame();
        this.start = null;
        this.frameOverlay.dispose();
        this.fireEvent('complete', frame);
    },
    getFrame: function(){
        var dx = this.point.x - this.start.x;
        var dy = this.point.y - this.start.y;
        var f = {
            sx: dx < 0 ? -1 : 1, 
            sy: dy < 0 ? -1 : 1,
            w: Math.abs(dx),
            h: Math.abs(dy)
        };
        f.x = Math.min(this.point.x, this.start.x) - this.basePosition.x;
        f.y = Math.min(this.point.y, this.start.y) - this.basePosition.y;
        return f;
    },
    onMouseMove: function(e){
        if(!this.start){
            return;
        }
        this.point = e.page;
        if(this.paintOverlay){
            this.paintFrame();
        }
    },
    paintFrame: function(x, y, w, h, rx, ry){
        var f = this.getFrame();
        this.frameOverlay.setStyles({
            'left': f.x + 'px',
            'top': f.y + 'px',
            'width': f.w + 'px',
            'height': f.h + 'px'
        })
    }
});
