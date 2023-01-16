from copy import copy
import numpy as np

# Custom
import pypattern as pyp

# other assets
from . import sleeves
from . import collars

class BodiceFrontHalf(pyp.Panel):
    def __init__(self, name, body, design) -> None:
        super().__init__(name)

        design = design['bodice']
        # account for ease in basic measurements
        m_bust = body['bust'] + design['ease']['v']
        m_waist = body['waist'] + design['ease']['v']

        # sizes   
        max_len = body['waist_over_bust_line']
        bust_point = body['bust_points'] / 2

        front_frac = (body['bust'] - body['back_width']) / 2 / body['bust'] 

        self.front_width = front_frac * m_bust
        waist = front_frac * m_waist
        shoulder_incl = (sh_tan:=np.tan(np.deg2rad(body['shoulder_incl']))) * self.front_width

        # side length is adjusted due to shoulder inclanation
        # for the correct sleeve fitting
        fb_diff = (front_frac - (0.5 - front_frac)) * body['bust']
        side_len = body['waist_line'] - sh_tan * fb_diff

        self.edges = pyp.esf.from_verts(
            [0, 0], 
            [-self.front_width, 0], 
            [-self.front_width, max_len], 
            [0, max_len + shoulder_incl], 
            loop=True
        )

        # Side dart
        bust_line = body['waist_line'] - body['bust_line']
        side_d_depth = 0.8 * (self.front_width - bust_point)    # NOTE: calculated value 
        side_d_width = max_len - side_len
        s_edge, s_dart_edges, side_interface = pyp.ops.cut_into_edge(
            pyp.esf.dart_shape(side_d_width, side_d_depth), 
            self.edges[1], 
            offset=bust_line + side_d_width / 2, right=True)
        self.edges.substitute(1, s_edge)
        self.stitching_rules.append(
            (pyp.Interface(self, s_dart_edges[0]), pyp.Interface(self, s_dart_edges[1])))

        # Bottom dart
        bottom_d_width = (self.front_width - waist) * 2 / 3

        b_edge, b_dart_edges, b_interface = pyp.ops.cut_into_edge(
            pyp.esf.dart_shape(bottom_d_width, 1. * bust_line), 
            self.edges[0], 
            offset=bust_point, right=True)
        self.edges.substitute(0, b_edge)
        self.stitching_rules.append(
            (pyp.Interface(self, b_dart_edges[0]), pyp.Interface(self, b_dart_edges[1])))

        # Take some fabric from side in the bottom 
        b_edge[-1].end[0] = - (waist + bottom_d_width)

        # Interfaces
        self.interfaces = {
            'outside':  pyp.Interface(self, side_interface),   # side_interface,    # pyp.Interface(self, [side_interface]),  #, self.edges[-3]]),
            'inside': pyp.Interface(self, self.edges[-1]),
            'shoulder': pyp.Interface(self, self.edges[-2]),
            'bottom': pyp.Interface(self, b_interface),
            
            # Reference to the corner for sleeve and collar projections
            'shoulder_corner': pyp.Interface(self, [self.edges[-3], self.edges[-2]]),
            'collar_corner': pyp.Interface(self, [self.edges[-2], self.edges[-1]])
        }

        # default placement
        self.translate_by([0, body['height'] - body['head_l'] - max_len, 0])


class BodiceBackHalf(pyp.Panel):
    """Panel for the front/back of upper garments"""

    def __init__(self, name, body, design) -> None:
        super().__init__(name)

        design = design['bodice']

        # account for ease in basic measurements
        m_bust = body['bust'] + design['ease']['v']
        m_waist = body['waist'] + design['ease']['v']

        # Overall measurements
        length = body['waist_line']
        back_fraction = body['back_width'] / body['bust'] / 2
        
        self.back_width = back_fraction * m_bust
        waist = back_fraction * m_waist
        waist_width = self.back_width - (self.back_width - waist) / 3   # slight inclanation on the side

        shoulder_incl = np.tan(np.deg2rad(body['shoulder_incl'])) * self.back_width

        # Base edge loop
        self.edges = pyp.esf.from_verts(
            [0, 0], 
            [-waist_width, 0],
            [-self.back_width, body['waist_line'] - body['bust_line']],  # from the bottom
            [-self.back_width, length],   # DRAFT shoulder_width   # Take some fabric from the shoulders
            [0, length + shoulder_incl],   # Add some fabric for the neck (inclanation of shoulders)
            loop=True)
        
        self.interfaces = {
            'outside': pyp.Interface(self, [self.edges[1], self.edges[2]]),  #, self.edges[3]]),
            'inside': pyp.Interface(self, self.edges[-1]),
            'shoulder': pyp.Interface(self, self.edges[-2]),
            # Reference to the corners for sleeve and collar projections
            'shoulder_corner': pyp.Interface(self, pyp.EdgeSequence(self.edges[-3], self.edges[-2])),
            'collar_corner': pyp.Interface(self, pyp.EdgeSequence(self.edges[-2], self.edges[-1]))
        }

        # Bottom dart as cutout -- for straight line
        bottom_d_width = (self.back_width - waist) * 2 / 3
        bottom_d_depth = 0.9 * (length - body['bust_line'])  # calculated value
        bottom_d_position = body['bust_points'] / 2

        b_edge, b_dart_edges, b_interface = pyp.ops.cut_into_edge(
            pyp.esf.dart_shape(bottom_d_width, bottom_d_depth), self.edges[0], 
            offset=bottom_d_position, right=True)

        self.edges.substitute(0, b_edge)
        self.interfaces['bottom'] = pyp.Interface(self, b_interface)

        # default placement
        self.translate_by([0, body['height'] - body['head_l'] - length, 0])

        # Stitch the dart
        self.stitching_rules.append((pyp.Interface(self, b_dart_edges[0]), pyp.Interface(self, b_dart_edges[1])))


class FittedShirtHalf(pyp.Component):
    """Definition of a simple T-Shirt"""

    def __init__(self, name, body, design) -> None:
        super().__init__(name)

        # Torso
        self.ftorso = BodiceFrontHalf(f'{name}_ftorso', body, design).translate_by([0, 0, 20])
        self.btorso = BodiceBackHalf(f'{name}_btorso', body, design).translate_by([0, 0, -20])

        # Sleeves
        if design['bodice']['sleeve_shape']['v']:
            
            incl = design['sleeve']['inclanation']['v']
            diff = self.ftorso.front_width - self.btorso.back_width

            self.sleeve = sleeves.SleeveOpening(name, body, incl, depth_diff=diff)

            # DEBUG 
            # front_sl = sleeves.ArmholeSquareSide('', body, design, shift=0, incl=incl + diff)
            # back_sl = sleeves.ArmholeSquareSide('', body, design, shift=0, incl=incl)
            
            _, f_sleeve_int = pyp.ops.cut_corner(
                self.sleeve.interfaces['in_front_shape'].projecting_edges(), 
                self.ftorso.interfaces['shoulder_corner'])
            _, b_sleeve_int = pyp.ops.cut_corner(
                self.sleeve.interfaces['in_back_shape'].projecting_edges(), 
                self.btorso.interfaces['shoulder_corner'])

            if design['bodice']['sleeveless']['v']:  
                # No sleeve component, only the cut remains
                del self.sleeve
            else:
                pass
                # FIXME merging f&b into one interface results in 
                # edge ordering ambiguity
                self.stitching_rules.append((self.sleeve.interfaces['in_front'], f_sleeve_int))
                self.stitching_rules.append((self.sleeve.interfaces['in_back'], b_sleeve_int))

            # DRAFT
            # sleeve_type = getattr(sleeves, design_opt['bodice']['sleeves']['v'])
            # self.sleeve = sleeve_type(f'{name}_sl', body_opt, design_opt, shift=2)   #DRAFT 
            # if isinstance(self.sleeve, pyp.Component):
            #     # Order of edges updated after (autonorm)..
            #     _, fr_sleeve_int = pyp.ops.cut_corner(self.sleeve.interfaces[0].projecting_edges(), self.ftorso.interfaces['shoulder_corner'])
            #     _, br_sleeve_int = pyp.ops.cut_corner(self.sleeve.interfaces[1].projecting_edges(), self.btorso.interfaces['shoulder_corner'])

            #     # Sleeves are connected by new interfaces
            #     self.stitching_rules.append((self.sleeve.interfaces[0], fr_sleeve_int))
            #     self.stitching_rules.append((self.sleeve.interfaces[1], br_sleeve_int))
            # else:   # it's just an edge sequence to define sleeve shape
            #     # Simply do the projection -- no new stitches needed
            #     pyp.ops.cut_corner(self.sleeve[0], self.ftorso.interfaces['shoulder_corner'])
            #     pyp.ops.cut_corner(self.sleeve[1], self.btorso.interfaces['shoulder_corner'])

        # Collars
        # TODO collars with extra panels!
        # Front
        collar_type = getattr(collars, design['bodice']['f_collar']['v'])
        f_collar = collar_type("", design['bodice']['fc_depth']['v'], body['neck_w'])
        pyp.ops.cut_corner(f_collar, self.ftorso.interfaces['collar_corner'])
        # Back
        collar_type = getattr(collars, design['bodice']['b_collar']['v'])
        b_collar = collar_type("", design['bodice']['bc_depth']['v'], body['neck_w'])
        pyp.ops.cut_corner(b_collar, self.btorso.interfaces['collar_corner'])

        self.stitching_rules.append((self.ftorso.interfaces['outside'], self.btorso.interfaces['outside']))   # sides
        self.stitching_rules.append((self.ftorso.interfaces['shoulder'], self.btorso.interfaces['shoulder']))  # tops

        self.interfaces = [
            self.ftorso.interfaces['inside'],  
            self.btorso.interfaces['inside'],

            # bottom
            self.ftorso.interfaces['bottom'],
            self.btorso.interfaces['bottom'],
        ]


class FittedShirt(pyp.Component):
    """Panel for the front of upper garments with darts to properly fit it to the shape"""

    def __init__(self, body, design) -> None:
        name_with_params = f"{self.__class__.__name__}"
        super().__init__(name_with_params)

        # TODO resolving names..
        self.right = FittedShirtHalf(f'right', body, design)
        self.left = FittedShirtHalf(f'left', body, design).mirror()

        self.stitching_rules.append((self.right.interfaces[0], self.left.interfaces[0]))
        self.stitching_rules.append((self.right.interfaces[1], self.left.interfaces[1]))

        self.interfaces = [   # Bottom connection
            self.right.interfaces[2],
            self.right.interfaces[3],
            self.left.interfaces[2],
            self.left.interfaces[3],
        ]
