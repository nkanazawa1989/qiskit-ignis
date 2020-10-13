# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""

"""

from qiskit.ignis.experiments.calibration import workflow
from qiskit.qobj.utils import MeasLevel, MeasReturnType
from qiskit.result import Result


class AnalysisWorkFlow:
    """Definition of workflow of measurement data processing."""
    def __init__(self,
                 average: bool = True,
                 shots: int = 1024):
        """Create new workflow.

        Args:
            average: Set `True` to average outcomes.
            shots: Number of shots, default to 1024.
        """
        self.root_node = None
        self.average = average
        self.shots = shots

    def meas_return(self):
        """Return appropriate measurement format to execute this analysis chain."""
        if AnalysisWorkFlow.check_discriminator(self.root_node):
            # if discriminator is defined, return type should be single.
            # quantum state cannot be discriminated with averaged IQ coordinate.
            return MeasReturnType.SINGLE
        return MeasReturnType.AVERAGE if self.average else MeasReturnType.SINGLE

    def meas_level(self):
        """Return appropriate measurement level to execute this analysis chain."""
        kernel = AnalysisWorkFlow.check_kernel(self.root_node)
        if kernel and isinstance(kernel, workflow.SystemKernel):
            discriminator = AnalysisWorkFlow.check_discriminator(self.root_node)
            if discriminator and isinstance(discriminator, workflow.SystemDiscriminator):
                # classified level if both system kernel and discriminator are defined
                return MeasLevel.CLASSIFIED
            # kerneled level if only system kernel is defined
            return MeasLevel.KERNELED
        # otherwise raw level is requested
        return MeasLevel.RAW

    def format_data(self, result: Result):
        """Format qiskit result data."""
        if not self.root_node:
            return result

        formatted_data = self.root_node.format_data(
            data=result,
            shots=self.shots
        )
        if self.average:
            pass

        return formatted_data

    @classmethod
    def check_kernel(cls, node: workflow.AnalysisRoutine):
        """Return stored kernel in the workflow."""
        if not node.child:
            return None

        if isinstance(node, workflow.Kernel):
            return node
        else:
            return cls.check_kernel(node.child)

    @classmethod
    def check_discriminator(cls, node: workflow):
        """Return stored discriminator in the workflow."""
        if not node.child:
            return None

        if isinstance(node, workflow.Kernel):
            return node
        else:
            return cls.check_discriminator(node.child)


class CalibrationWorkflow(AnalysisWorkFlow):

    def __init__(self,
                 iq_method: str = 'real',
                 average: bool = True,
                 shots: int = 1024):
        super().__init__(
            average=average,
            shots=shots
        )
        # add system kernel
        self.root_node = workflow.SystemKernel()

        # add post-processing for IQ data
        if iq_method == 'real':
            self.root_node.append(workflow.RealNumbers)
        elif iq_method == 'imag':
            self.root_node.append(workflow.ImagNumbers)


class CircuitWorkflow(AnalysisWorkFlow):

    def __init__(self,
                 shots: int = 1024):
        super().__init__(
            average=False,
            shots=shots
        )
        # add system kernel
        self.root_node = workflow.SystemKernel()

        # add system discriminator
        self.root_node.append(workflow.SystemDiscriminator())
