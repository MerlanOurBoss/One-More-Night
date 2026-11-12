// Final step: reduces colors per channel with a 4x4 Bayer dither, in low-res pixels.
// Used by the RawImage that shows the low-res render texture on screen.
Shader "OneMoreNight/PS1 Output"
{
    Properties
    {
        [PerRendererData] _MainTex ("Render Texture", 2D) = "black" {}
        _Levels ("Levels Per Channel", Float) = 32
        _Dither ("Dither Strength", Range(0, 1)) = 1
    }

    SubShader
    {
        Tags { "Queue" = "Overlay" "RenderType" = "Opaque" "IgnoreProjector" = "True" }
        Cull Off
        ZWrite Off
        ZTest Always
        Blend Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment Frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            float4 _MainTex_TexelSize;
            float _Levels;
            float _Dither;
            // Global, from the settings: 0 leaves the image as it is, above 0 lifts the dark, below 0 sinks it. Black stays black.
            float _PS1Brightness;

            static const float Bayer[16] = { 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5 };

            float4 Frag(v2f_img input) : SV_Target
            {
                // Levels are counted in gamma space, as a display would show them.
                float3 color = LinearToGammaSpace(tex2D(_MainTex, input.uv).rgb);
                color = pow(max(color, 0.0), exp2(-_PS1Brightness));

                int2 pixel = int2(floor(input.uv * _MainTex_TexelSize.zw)) & 3;
                float threshold = (Bayer[pixel.y * 4 + pixel.x] + 0.5) / 16.0 - 0.5;

                float steps = _Levels - 1.0;
                color = round(color * steps + threshold * _Dither) / steps;
                return float4(GammaToLinearSpace(saturate(color)), 1.0);
            }
            ENDCG
        }
    }
}
