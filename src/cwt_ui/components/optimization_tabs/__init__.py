# Optimization tab renderers (Compute, Containers, Serverless, Commitment)

from cwt_ui.components.optimization_tabs.ec2_tab import render_ec2_tab
from cwt_ui.components.optimization_tabs.lambda_tab import render_lambda_tab
from cwt_ui.components.optimization_tabs.fargate_tab import render_fargate_tab
from cwt_ui.components.optimization_tabs.commitment_tab import render_commitment_tab

__all__ = ["render_ec2_tab", "render_lambda_tab", "render_fargate_tab", "render_commitment_tab"]
