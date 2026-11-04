// Common shader for every world material: vertex snapping, weak affine UVs,
// per-vertex lighting and fog to black. Globals are set by PS1Globals.
Shader "OneMoreNight/PS1 Lit"
{
    Properties
    {
        [MainTexture] _BaseMap ("Texture", 2D) = "white" {}
        [MainColor] _BaseColor ("Color", Color) = (1, 1, 1, 1)
        _Emission ("Emission", Color) = (0, 0, 0, 0)
        _Cutoff ("Alpha Cutout", Range(0, 1)) = 0
        // Off for the room shell, drawn first: snapped vertices would otherwise push walls through whatever hangs on them.
        [Enum(Off, 0, On, 1)] _ZWrite ("Depth Write", Float) = 1
        // For walls of a home with several rooms: they must still hide the next room, so keep depth write and push them back a little instead.
        _DepthBias ("Depth Bias", Float) = 0
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        Pass
        {
            Name "Forward"
            Tags { "LightMode" = "UniversalForward" }
            ZWrite [_ZWrite]
            Offset [_DepthBias], [_DepthBias]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment Frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_BaseMap);
            SAMPLER(sampler_BaseMap);

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4 _BaseColor;
                half4 _Emission;
                half _Cutoff;
            CBUFFER_END

            float2 _PS1SnapGrid;
            float _PS1Affine;
            float2 _PS1Fog;
            half3 _PS1FogColor;
            half3 _PS1Ambient;
            float _PS1LightCap;

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
                half4 color : COLOR;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                noperspective float2 uvAffine : TEXCOORD1;
                half3 light : TEXCOORD2;
                half fog : TEXCOORD3;
            };

            // Vertices behind the camera keep their position, otherwise big polygons tear when clipped.
            float4 SnapToGrid(float4 clipPos, float2 grid)
            {
                if (clipPos.w > 0.0)
                    clipPos.xy = floor(clipPos.xy / clipPos.w * grid + 0.5) / grid * clipPos.w;
                return clipPos;
            }

            half3 VertexLight(float3 positionWS, float3 normalWS)
            {
                Light mainLight = GetMainLight();
                half3 light = _PS1Ambient + mainLight.color * mainLight.distanceAttenuation * saturate(dot(normalWS, mainLight.direction));

                // Rendering layers keep a lamp in its own room: there are no shadows to stop it at the wall.
                uint renderingLayers = GetMeshRenderingLayer();
                int count = GetAdditionalLightsCount();
                for (int i = 0; i < count; i++)
                {
                    Light additional = GetAdditionalLight(i, positionWS);
                    if ((additional.layerMask & renderingLayers) != 0)
                        light += additional.color * min(additional.distanceAttenuation, _PS1LightCap) * saturate(dot(normalWS, additional.direction));
                }
                return light;
            }

            Varyings Vert(Attributes input)
            {
                Varyings output;
                float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(input.normalOS);

                output.positionCS = SnapToGrid(TransformWorldToHClip(positionWS), _PS1SnapGrid);
                output.uv = TRANSFORM_TEX(input.uv, _BaseMap);
                output.uvAffine = output.uv;
                output.light = VertexLight(positionWS, normalWS) * input.color.rgb;
                output.fog = saturate((_PS1Fog.y - distance(positionWS, _WorldSpaceCameraPos)) / (_PS1Fog.y - _PS1Fog.x));
                return output;
            }

            half4 Frag(Varyings input) : SV_Target
            {
                float2 uv = lerp(input.uv, input.uvAffine, _PS1Affine);
                half4 albedo = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, uv);
                clip(albedo.a - _Cutoff);
                half3 color = albedo.rgb * _BaseColor.rgb * input.light + _Emission.rgb;
                return half4(lerp(_PS1FogColor, color, input.fog), 1.0);
            }
            ENDHLSL
        }
    }
}
