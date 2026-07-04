$(document).ready(function(){
	//搜索框
	$(".top-sea form .text").focus(function(){
		if($(this).val()=="请输入关键字查询"){
			$(this).val("");
		}
		
	}).blur(function(){
		if($(this).val()==""){
		$(this).val("请输入关键字查询");
		}
	});
	// 内容切换
	$(".head ul li").mouseenter(function(){
		$(this).addClass("col").siblings().removeClass("col");
		var _index = $(this).index();
		$(this).parents("ul").siblings("a").eq(_index).addClass("one").siblings("a").removeClass("one");
		$(this).parents("ul").parents(".head").siblings(".cont").children('ul').eq(_index).show().siblings().hide();
	});


		//一级栏目切换
		$(".content .content-left ul li").mouseenter(function(){
			$(this).addClass("on").siblings("li").removeClass("on");
			$(".content-n").css("border","1px solid #118297");
			$(".lunbo").css("display","none");
			var index = $(this).index();
			$(this).parents("ul").parents(".content-left").siblings(".content-right").children('.tab').children("ul").eq(index).show().siblings().hide();
			$(".lunbo").hide();
		});

		$(".content").mouseleave(function(){
			$(".content-left ul li").removeClass("on");
			$(".content-right .lunbo").show();
			$(".content-right .tab").hide();
			$(".content-n").css("border","1px solid #fff");
		});
		$(".content-left").mouseenter(function(){
			$(".content-right .tab").show();
			$(".content-right .lunbo").hide();

		});



    //平台、设备和操作系统
    var system = {
        win: false,
        mac: false,
        xll: false,
        ipad:false
    };
//检测平台
    var p = navigator.platform;
    system.win = p.indexOf("Win") == 0;
    system.mac = p.indexOf("Mac") == 0;
    system.x11 = (p == "X11") || (p.indexOf("Linux") == 0);
    system.ipad = (navigator.userAgent.match(/iPad/i) != null)?true:false;
//跳转语句，如果是手机访问就自动跳转到wap.baidu.com页面
    if (system.win || system.mac || system.xll||system.ipad) {
        // alert("电脑");
        $(".pc-lunbo").show();
        $(".mob-lunbo").hide();

    } else {
        // alert("手机");
        $(".mob-lunbo").show();
        $(".pc-lunbo").hide();
    }



　if($(window).width()<=850){
　　　　　　　　$(".core>ul>li").unbind('mouseenter').unbind('mouseleave');  
　　　　　　}



$(".core>ul>li").each(function(){
	if($(this).find("p").html()==$(".column-left dl dt").html()){
		$(this).css("background","#09778b");
	}
})



})


